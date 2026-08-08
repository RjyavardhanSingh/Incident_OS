import logging
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.events.base import EventEnvelope
from app.models.incident import Incident
from app.models.investigation import (
    INVESTIGATION_STATUS_ANALYZING,
    INVESTIGATION_STATUS_COLLECTING,
    INVESTIGATION_STATUS_CREATED,
    STEP_STATUS_COMPLETED,
    STEP_STATUS_FAILED,
    STEP_STATUS_PENDING,
    STEP_STATUS_RUNNING,
    STEP_TOPIC_MAP,
    COLLECTION_STEPS,
    Investigation,
    InvestigationStep,
)
from app.investigation.state import all_steps_terminal, investigation_transition

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_investigation(session: AsyncSession, incident_id) -> Investigation:
    """Create the investigation record and its expected collection steps."""
    investigation = Investigation(
        incident_id=incident_id,
        status=INVESTIGATION_STATUS_CREATED,
    )
    session.add(investigation)
    await session.flush()
    for step_type in COLLECTION_STEPS:
        session.add(
            InvestigationStep(
                investigation_id=investigation.id,
                step_type=step_type,
                status=STEP_STATUS_PENDING,
            )
        )
    await session.commit()
    await session.refresh(investigation)
    return investigation


async def transition_investigation(
    session: AsyncSession, investigation_id, target: str
) -> Investigation | None:
    """Apply a legal investigation state transition."""
    investigation = await session.get(Investigation, investigation_id)
    if investigation is None:
        return None
    if not investigation_transition(investigation.status, target):
        raise ValueError(
            f"invalid investigation transition {investigation.status} -> {target}"
        )
    investigation.status = target
    investigation.updated_at = _now()
    await session.commit()
    await session.refresh(investigation)
    return investigation


async def get_investigation(session: AsyncSession, investigation_id) -> Investigation | None:
    return await session.get(Investigation, investigation_id)


async def list_steps(session: AsyncSession, investigation_id) -> list[InvestigationStep]:
    result = await session.execute(
        select(InvestigationStep)
        .where(InvestigationStep.investigation_id == investigation_id)
        .order_by(InvestigationStep.step_type)
    )
    return list(result.scalars().all())


async def claim_step(session: AsyncSession, step_id) -> tuple[InvestigationStep | None, str]:
    """Claim a step for work.

    Outcomes:
      "claimed"          - PENDING -> RUNNING
      "retry"            - FAILED -> RUNNING with attempt incremented
      "duplicate"        - already RUNNING/COMPLETED (idempotent skip)
      "missing"          - step does not exist
    """
    step = await session.get(InvestigationStep, step_id)
    if step is None:
        return None, "missing"
    now = _now()
    if step.status == STEP_STATUS_RUNNING:
        return step, "duplicate"
    if step.status == STEP_STATUS_COMPLETED:
        return step, "duplicate"
    if step.status == STEP_STATUS_PENDING:
        result = await session.execute(
            update(InvestigationStep)
            .where(
                InvestigationStep.id == step_id,
                InvestigationStep.status == STEP_STATUS_PENDING,
            )
            .values(status=STEP_STATUS_RUNNING, started_at=now, updated_at=now)
        )
        await session.commit()
        outcome = "claimed" if result.rowcount == 1 else "duplicate"
        return step, outcome
    if step.status == STEP_STATUS_FAILED:
        await session.execute(
            update(InvestigationStep)
            .where(
                InvestigationStep.id == step_id,
                InvestigationStep.status == STEP_STATUS_FAILED,
            )
            .values(
                status=STEP_STATUS_PENDING,
                attempt=step.attempt + 1,
                error=None,
                updated_at=now,
            )
        )
        await session.commit()
        result = await session.execute(
            update(InvestigationStep)
            .where(
                InvestigationStep.id == step_id,
                InvestigationStep.status == STEP_STATUS_PENDING,
            )
            .values(status=STEP_STATUS_RUNNING, started_at=now, updated_at=now)
        )
        await session.commit()
        outcome = "retry" if result.rowcount == 1 else "duplicate"
        return step, outcome
    return step, "unknown"


async def complete_step(session: AsyncSession, step_id) -> bool:
    result = await session.execute(
        update(InvestigationStep)
        .where(
            InvestigationStep.id == step_id,
            InvestigationStep.status == STEP_STATUS_RUNNING,
        )
        .values(status=STEP_STATUS_COMPLETED, completed_at=_now(), updated_at=_now())
    )
    await session.commit()
    return result.rowcount == 1


async def fail_step(session: AsyncSession, step_id, error: str) -> bool:
    result = await session.execute(
        update(InvestigationStep)
        .where(
            InvestigationStep.id == step_id,
            InvestigationStep.status == STEP_STATUS_RUNNING,
        )
        .values(status=STEP_STATUS_FAILED, error=error[:1024], updated_at=_now())
    )
    await session.commit()
    return result.rowcount == 1


async def advance_when_collection_terminal(session: AsyncSession, investigation_id) -> Investigation | None:
    """Advance COLLECTING -> ANALYZING only when every step is terminal.

    This is the correlation gate: correlation must never run before all
    required collection steps reach a terminal state.
    """
    investigation = await session.get(Investigation, investigation_id)
    if investigation is None:
        return None
    if investigation.status != INVESTIGATION_STATUS_COLLECTING:
        return None
    steps = await list_steps(session, investigation_id)
    if not all_steps_terminal([s.status for s in steps]):
        return None
    return await transition_investigation(session, investigation_id, INVESTIGATION_STATUS_ANALYZING)


def publish_investigation_events(publisher, investigation: Investigation, incident: Incident) -> None:
    """Publish investigation.started and every evidence.*.requested event."""
    publisher.publish(
        EventEnvelope(
            event_type="investigation.started",
            incident_id=incident.id,
            investigation_id=investigation.id,
            producer="orchestrator",
            payload={"service": incident.service},
        )
    )
    payload = {
        "service": incident.service,
        "window_start": incident.started_at.isoformat(),
    }
    for step_type, topic in STEP_TOPIC_MAP.items():
        publisher.publish(
            EventEnvelope(
                event_type=topic,
                incident_id=incident.id,
                investigation_id=investigation.id,
                producer="orchestrator",
                payload={**payload, "step_type": step_type},
            )
        )
