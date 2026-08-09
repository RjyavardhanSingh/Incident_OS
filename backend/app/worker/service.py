import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.correlation import engine as correlation_engine
from app.events.base import EventEnvelope
from app.investigation import service as investigation_service
from app.models.correlation import (
    CORRELATION_RUN_STATUS_COMPLETED,
    CorrelationRun,
)
from app.models.evidence import Evidence
from app.models.investigation import (
    INVESTIGATION_STATUS_READY,
    INVESTIGATION_STATUS_VERIFYING,
    InvestigationStep,
    STEP_TOPIC_MAP,
)
from app.models.verification import (
    VERIFICATION_RUN_STATUS_COMPLETED,
    VerificationRun,
)
from app.rootcause import engine as root_cause_engine
from app.sources.contract import CollectionContext, EvidenceRecord
from app.sources.registry import close_source, create_source
from app.verification import engine as verification_engine

logger = logging.getLogger(__name__)

CORRELATION_EVENT_TYPE = "correlation.requested"
VERIFICATION_EVENT_TYPE = "verification.requested"


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


async def _persist_evidence(
    session: AsyncSession,
    records: list[EvidenceRecord],
    investigation_id,
    incident_id,
) -> int:
    """Insert fresh evidence or link already-stored evidence to the investigation.

    Store-backed sources return records with ``evidence_id`` set (rows already
    exist); live sources return fresh records to insert.
    """
    linked = 0
    for record in records:
        if record.evidence_id is not None:
            row = await session.get(Evidence, record.evidence_id)
            if row is None:
                continue
            row.investigation_id = investigation_id
            linked += 1
        else:
            session.add(
                Evidence(
                    source=record.source,
                    service=record.service,
                    signal=record.signal,
                    timestamp=record.timestamp,
                    severity=record.severity,
                    trace_id=record.trace_id,
                    span_id=record.span_id,
                    incident_id=incident_id,
                    investigation_id=investigation_id,
                    payload=record.payload or {},
                )
            )
            linked += 1
    if records:
        await session.commit()
    return linked


async def _collect_evidence(session: AsyncSession, step_type: str, envelope: EventEnvelope) -> list[EvidenceRecord]:
    payload = envelope.payload
    service = payload.get("service")
    window_start = _parse_iso(payload["window_start"]) if payload.get("window_start") else None
    if window_start is None:
        window_start = datetime(1970, 1, 1, tzinfo=timezone.utc)

    context = CollectionContext(
        incident_id=envelope.incident_id,
        investigation_id=envelope.investigation_id,
        service=service or "unknown",
        window_start=window_start,
    )
    source = create_source(step_type, session)
    try:
        return await source.collect(context)
    finally:
        await close_source(source)


async def handle_evidence_requested(
    session: AsyncSession,
    publisher,
    envelope: EventEnvelope,
) -> None:
    """Collect evidence for one requested step and update its state.

    Idempotency: duplicates are detected by the step claim; only PENDING steps
    run work, and a retry (FAILED) increments attempt without a new step.
    """
    investigation_id = envelope.investigation_id
    step_type = envelope.payload.get("step_type")
    step: InvestigationStep | None = None
    for candidate in await investigation_service.list_steps(session, investigation_id):
        if candidate.step_type == step_type:
            step = candidate
            break
    if step is None:
        logger.error("no step %s for investigation %s", step_type, investigation_id)
        return

    _step, claim = await investigation_service.claim_step(session, step.id)
    if claim in ("duplicate", "missing"):
        logger.info("skip %s step %s claim=%s", step_type, step.id, claim)
        return

    records: list[EvidenceRecord] = []
    try:
        records = await _collect_evidence(session, step_type, envelope)
        count = await _persist_evidence(
            session, records, investigation_id, envelope.incident_id
        )
        if not await investigation_service.complete_step(session, step.id):
            logger.error("step %s could not be marked COMPLETED", step.id)
        outcome = "COMPLETED"
        logger.info("collected %s evidence for step %s", count, step_type)
    except Exception as exc:
        await session.rollback()
        await investigation_service.fail_step(session, step.id, str(exc))
        logger.exception("step %s failed: %s", step.id, exc)
        raise

    publisher.publish(
        EventEnvelope(
            event_type="evidence.collected",
            incident_id=envelope.incident_id,
            investigation_id=investigation_id,
            producer=f"{step_type}-worker",
            payload={
                "step_type": step_type,
                "status": outcome,
                "evidence_count": count,
            },
        )
    )

    advanced = await investigation_service.advance_when_collection_terminal(session, investigation_id)
    if advanced is not None:
        logger.info(
            "investigation %s advanced to %s (all steps terminal)",
            investigation_id,
            advanced.status,
        )
        publisher.publish(
            EventEnvelope(
                event_type=CORRELATION_EVENT_TYPE,
                incident_id=envelope.incident_id,
                investigation_id=investigation_id,
                producer="orchestrator",
                payload={"service": envelope.payload.get("service")},
            )
        )
        # Correlation is on the critical path; flush so the control event is not
        # stranded in the producer buffer when the worker goes idle.
        publisher.flush()


async def handle_correlation_requested(session: AsyncSession, publisher, envelope: EventEnvelope) -> None:
    """Run deterministic correlation once per investigation.

    At-least-once delivery is guarded: a COMPLETED run means this investigation
    already correlated, so the redelivery is skipped (no duplicate candidates).
    """
    investigation_id = envelope.investigation_id
    run = (
        await session.execute(
            select(CorrelationRun)
            .where(
                CorrelationRun.investigation_id == investigation_id,
                CorrelationRun.status == CORRELATION_RUN_STATUS_COMPLETED,
            )
            .limit(1)
        )
    ).scalars().first()
    if run is not None:
        logger.info("correlation already completed for %s; skip duplicate", investigation_id)
        return

    try:
        run, candidates = await correlation_engine.run_for_investigation(
            session, investigation_id
        )
        await investigation_service.transition_investigation(
            session, investigation_id, INVESTIGATION_STATUS_VERIFYING
        )
    except Exception as exc:
        logger.exception("correlation failed for %s: %s", investigation_id, exc)
        raise

    publisher.publish(
        EventEnvelope(
            event_type="correlation.completed",
            incident_id=envelope.incident_id,
            investigation_id=investigation_id,
            producer="correlation-worker",
            payload={
                "candidate_count": len(candidates),
                "failed_sources": run.failed_sources,
            },
        )
    )
    publisher.publish(
        EventEnvelope(
            event_type=VERIFICATION_EVENT_TYPE,
            incident_id=envelope.incident_id,
            investigation_id=investigation_id,
            producer="correlation-worker",
            payload={"candidate_count": len(candidates)},
        )
    )
    publisher.flush()


async def handle_verification_requested(session: AsyncSession, publisher, envelope: EventEnvelope) -> None:
    """Verify every correlation candidate once per investigation.

    At-least-once delivery is guarded: a COMPLETED run means verification already
    ran, so redeliveries are skipped (no duplicate results).
    """
    investigation_id = envelope.investigation_id
    run = (
        await session.execute(
            select(VerificationRun)
            .where(
                VerificationRun.investigation_id == investigation_id,
                VerificationRun.status == VERIFICATION_RUN_STATUS_COMPLETED,
            )
            .limit(1)
        )
    ).scalars().first()
    if run is not None:
        logger.info("verification already completed for %s; skip duplicate", investigation_id)
        return

    try:
        run, results = await verification_engine.run_for_investigation(
            session, investigation_id
        )
        root_cause = await root_cause_engine.select_for_investigation(
            session, investigation_id
        )
        await investigation_service.transition_investigation(
            session, investigation_id, INVESTIGATION_STATUS_READY
        )
    except Exception as exc:
        logger.exception("verification failed for %s: %s", investigation_id, exc)
        raise

    publisher.publish(
        EventEnvelope(
            event_type="verification.completed",
            incident_id=envelope.incident_id,
            investigation_id=investigation_id,
            producer="verification-worker",
            payload={
                "verified": run.verified_count,
                "contradicted": run.contradicted_count,
                "unverified": run.unverified_count,
            },
        )
    )
    publisher.publish(
        EventEnvelope(
            event_type="rootcause.completed",
            incident_id=envelope.incident_id,
            investigation_id=investigation_id,
            producer="verification-worker",
            payload={
                "selection_mode": root_cause.selection_mode if root_cause else None,
                "root_cause_type": root_cause.root_cause_type if root_cause else None,
            },
        )
    )
    publisher.flush()


async def handle_envelope(session_factory, publisher, envelope: EventEnvelope) -> None:
    async with session_factory() as session:
        if envelope.event_type in STEP_TOPIC_MAP.values():
            await handle_evidence_requested(session, publisher, envelope)
        elif envelope.event_type == CORRELATION_EVENT_TYPE:
            await handle_correlation_requested(session, publisher, envelope)
        elif envelope.event_type == VERIFICATION_EVENT_TYPE:
            await handle_verification_requested(session, publisher, envelope)
        else:
            logger.info("ignoring unhandled event_type=%s", envelope.event_type)
