"""Deterministic correlation engine.

Loads an investigation's evidence, evaluates the deterministic rules, persists
a CorrelationRun with its RootCauseCandidates, and records which evidence
sources failed during collection.
"""
import logging
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.correlation.rules import run_correlation
from app.models.correlation import (
    CANDIDATE_STATUS_PENDING,
    CORRELATION_RUN_STATUS_COMPLETED,
    CORRELATION_RUN_STATUS_RUNNING,
    CorrelationRun,
    RootCauseCandidate,
)
from app.models.evidence import Evidence
from app.models.incident import Incident
from app.models.investigation import STEP_STATUS_FAILED, Investigation, InvestigationStep

logger = logging.getLogger(__name__)

DEPLOYMENT_WINDOW = timedelta(seconds=300)


def _evidence_summary(ev: Evidence) -> str:
    payload = ev.payload or {}
    if ev.signal == "log":
        message = payload.get("body") or payload.get("message") or ""
        return f"{ev.severity} log: {message[:120]}"
    if ev.signal == "metric":
        metric = payload.get("metric", "?")
        return f"metric {metric}: {payload.get('value', '')}"
    if ev.signal == "trace":
        return (
            f"trace {ev.trace_id or '?'} span {ev.span_id or '?'} "
            f"status={payload.get('status_code') or payload.get('status') or 'OK'}"
        )
    observation = payload.get("observation", "?")
    return f"observation {observation}: {payload}"


def _chain_entry(ev: Evidence) -> dict:
    return {
        "evidence_id": str(ev.id),
        "source": ev.source,
        "signal": ev.signal,
        "timestamp": ev.timestamp.isoformat(),
        "summary": _evidence_summary(ev),
    }


async def run_for_investigation(
    session: AsyncSession, investigation_id: UUID
) -> tuple[CorrelationRun, list[RootCauseCandidate]]:
    """Run deterministic correlation and persist the run + candidates."""
    run = CorrelationRun(investigation_id=investigation_id, status=CORRELATION_RUN_STATUS_RUNNING)
    session.add(run)
    await session.commit()

    investigation = await session.get(Investigation, investigation_id)
    incident = await session.get(Incident, investigation.incident_id)
    steps = (
        (await session.execute(
            select(InvestigationStep)
            .where(InvestigationStep.investigation_id == investigation_id)
        ))
        .scalars()
        .all()
    )
    failed_sources = sorted(
        step.step_type for step in steps if step.status == STEP_STATUS_FAILED
    )
    run.failed_sources = failed_sources

    evidence = (
        (await session.execute(
            select(Evidence)
            .where(Evidence.investigation_id == investigation_id)
            .order_by(Evidence.timestamp.asc())
        ))
        .scalars()
        .all()
    )

    drafts = run_correlation(incident, list(evidence), DEPLOYMENT_WINDOW)

    candidates: list[RootCauseCandidate] = []
    for rank, draft in enumerate(drafts, start=1):
        candidate = RootCauseCandidate(
            investigation_id=investigation_id,
            run_id=run.id,
            rank=rank,
            root_cause_type=draft.root_cause_type,
            title=draft.title,
            summary=draft.summary,
            confidence=draft.confidence,
            status=CANDIDATE_STATUS_PENDING,
            evidence_chain=[_chain_entry(ev) for ev in draft.evidence],
            related_services=draft.related_services,
        )
        session.add(candidate)
        candidates.append(candidate)

    run.status = CORRELATION_RUN_STATUS_COMPLETED
    run.candidate_count = len(candidates)
    await session.commit()

    logger.info(
        "correlation for investigation %s: %d candidates, failed_sources=%s",
        investigation_id,
        len(candidates),
        failed_sources,
    )
    return run, candidates
