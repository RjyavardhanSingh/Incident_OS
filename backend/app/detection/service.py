from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.detection.rules import (
    DEFAULT_RULES,
    SEVERITY_BY_RULE,
    evaluate_rule,
)
from app.models.evidence import Evidence
from app.models.incident import (
    INCIDENT_STATUS_OPEN,
    DetectionRule,
    Incident,
)

DEFAULT_SERVICE = "unknown"


def _title(violation) -> str:
    return (
        f"{violation.rule_name} on {violation.service} "
        f"(value={violation.value}, threshold={violation.threshold})"
    )


async def _has_open_incident(
    session: AsyncSession, service: str, rule_id, window_seconds: int
) -> bool:
    stmt = select(Incident.id).where(
        Incident.service == service,
        Incident.detection_rule_id == rule_id,
        Incident.status == INCIDENT_STATUS_OPEN,
    )
    result = await session.execute(stmt)
    return result.first() is not None


async def seed_default_rules(session: AsyncSession) -> None:
    for spec in DEFAULT_RULES:
        stmt = select(DetectionRule).where(DetectionRule.name == spec["name"])
        existing = (await session.execute(stmt)).scalars().first()
        if existing is None:
            session.add(DetectionRule(**spec))
    await session.commit()


async def evaluate(session: AsyncSession, reference: datetime | None = None) -> list[Incident]:
    if reference is None:
        reference = datetime.now(timezone.utc)

    rules_stmt = select(DetectionRule).where(DetectionRule.enabled.is_(True))
    rules = (await session.execute(rules_stmt)).scalars().all()
    if not rules:
        return []

    max_window = max(rule.window_seconds for rule in rules)
    window_start = reference - timedelta(seconds=max_window)

    evidence_stmt = select(Evidence).where(Evidence.timestamp >= window_start)
    evidence = (await session.execute(evidence_stmt)).scalars().all()

    created: list[Incident] = []
    for rule in rules:
        rule_window_start = reference - timedelta(seconds=rule.window_seconds)
        relevant = [ev for ev in evidence if ev.timestamp >= rule_window_start]
        if rule.target_service:
            relevant = [ev for ev in relevant if ev.service == rule.target_service]
        violations = evaluate_rule(relevant, rule)
        for violation in violations:
            if await _has_open_incident(
                session, violation.service, rule.id, rule.window_seconds
            ):
                continue
            incident = Incident(
                title=_title(violation),
                service=violation.service,
                severity=SEVERITY_BY_RULE.get(rule.rule_type, "minor"),
                status=INCIDENT_STATUS_OPEN,
                detection_rule_id=rule.id,
                detection_rule_name=rule.name,
                started_at=window_start,
                payload={
                    "rule_type": rule.rule_type,
                    "value": violation.value,
                    "threshold": violation.threshold,
                    "detail": violation.detail,
                },
            )
            session.add(incident)
            created.append(incident)

    await session.commit()
    return created
