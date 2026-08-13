"""Deterministic correlation rules.

Rules are pure functions over (incident, evidence) and produce candidate root
causes with evidence chains. No I/O, no randomness, no LLM: fully testable and
deterministic. Candidate root causes from here are the input to verification.
"""
from dataclasses import dataclass, field
from datetime import timedelta

from app.detection.rules import (
    METRIC_HTTP_DURATION,
    METRIC_KAFKA_CONSUMER_LAG,
    RULE_DEPLOYMENT_REGRESSION,
    RULE_KAFKA_CONSUMER_LAG,
    RULE_REDIS_ERROR_RATE,
    _status_code,
)
from app.models.evidence import Evidence
from app.models.incident import Incident

RC_DEPLOYMENT_CHANGE = "deployment_change"
RC_DEPENDENCY_FAILURE = "dependency_failure"
RC_REDIS_PRESSURE = "redis_pressure"
RC_KAFKA_LAG = "kafka_consumer_lag"
RC_DATABASE_CONTENTION = "database_contention"
RC_ERROR_BURST = "error_burst"

DEPLOYMENT_SOURCE = "deployment"


@dataclass
class CandidateDraft:
    root_cause_type: str
    title: str
    summary: str
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    related_services: list[str] = field(default_factory=list)


def _sorted_chain(evidence: list[Evidence]) -> list[Evidence]:
    return sorted(evidence, key=lambda ev: ev.timestamp)


def _is_deployment(ev: Evidence) -> bool:
    payload = ev.payload or {}
    return (
        payload.get("source_type") == DEPLOYMENT_SOURCE
        or payload.get("attributes", {}).get("source_type") == DEPLOYMENT_SOURCE
    )


def _is_error_log(ev: Evidence) -> bool:
    return ev.signal == "log" and ev.severity == "ERROR"


def _is_error_metric(ev: Evidence) -> bool:
    payload = ev.payload or {}
    if payload.get("metric") != METRIC_HTTP_DURATION:
        return False
    return any(
        (code := _status_code(dp)) is not None and code >= 500
        for dp in payload.get("datapoints", [])
    )


def _is_error_span(ev: Evidence) -> bool:
    payload = ev.payload or {}
    return (
        ev.signal == "trace"
        and payload.get("status_code") in ("STATUS_CODE_ERROR", "ERROR", 2)
    ) or payload.get("attributes", {}).get("status_code") in ("STATUS_CODE_ERROR", "ERROR")


def _observation(ev: Evidence, kind: str) -> dict | None:
    payload = ev.payload or {}
    if payload.get("observation") == kind:
        return payload
    return None


def rule_deployment_change(incident: Incident, evidence: list[Evidence], window: timedelta) -> CandidateDraft | None:
    deployments = [
        ev for ev in evidence if _is_deployment(ev)
        and ev.service == incident.service
        and ev.timestamp >= incident.started_at - window
    ]
    if not deployments:
        return None
    errors = [
        ev for ev in evidence
        if ev.service == incident.service
        and (_is_error_log(ev) or _is_error_metric(ev) or _is_error_span(ev))
    ]
    confidence = 0.9 if errors else 0.7
    chain = _sorted_chain(deployments + errors)
    return CandidateDraft(
        root_cause_type=RC_DEPLOYMENT_CHANGE,
        title=f"Deployment change on {incident.service}",
        summary=(
            f"Deployment evidence present near incident start "
            f"({len(deployments)} deployment record(s)); "
            f"{'error signals observed after deployment' if errors else 'no error signals yet'}."
        ),
        confidence=confidence,
        evidence=chain,
        related_services=[incident.service],
    )


def rule_dependency_failure(incident: Incident, evidence: list[Evidence]) -> CandidateDraft | None:
    dependents = {
        ev.service
        for ev in evidence
        if ev.service != incident.service
        and (_is_error_log(ev) or _is_error_metric(ev) or _is_error_span(ev))
    }
    if not dependents:
        return None
    errors = [
        ev for ev in evidence
        if ev.service in dependents
        and (_is_error_log(ev) or _is_error_metric(ev) or _is_error_span(ev))
    ]
    confidence = min(0.8, 0.6 + 0.1 * len(dependents))
    return CandidateDraft(
        root_cause_type=RC_DEPENDENCY_FAILURE,
        title=f"Dependency failure from {', '.join(sorted(dependents))}",
        summary=(
            f"{len(dependents)} dependent service(s) show errors "
            f"({len(errors)} error records) while {incident.service} is failing."
        ),
        confidence=round(confidence, 3),
        evidence=_sorted_chain(errors),
        related_services=sorted(dependents),
    )


def rule_redis_pressure(incident: Incident, evidence: list[Evidence]) -> CandidateDraft | None:
    error_logs = [
        ev for ev in evidence
        if ev.service == incident.service and _is_error_log(ev)
        and "redis" in str(ev.payload).lower()
    ]
    supporting = incident.payload.get("rule_type") == RULE_REDIS_ERROR_RATE
    if not error_logs:
        return None
    redis_obs = [ev for ev in evidence if _observation(ev, "clients")]
    connected = [ev for ev in redis_obs]
    chain = _sorted_chain(error_logs + connected)
    confidence = 0.8 if supporting else 0.6
    return CandidateDraft(
        root_cause_type=RC_REDIS_PRESSURE,
        title=f"Redis pressure affecting {incident.service}",
        summary=(
            f"Redis error logs observed ({len(error_logs)}) and live Redis probes "
            f"present ({len(connected)} client observations); "
            f"incident is redis-related={supporting}."
        ),
        confidence=confidence,
        evidence=chain,
        related_services=[incident.service, "redis"],
    )


def rule_kafka_lag(incident: Incident, evidence: list[Evidence]) -> CandidateDraft | None:
    summaries = [ev for ev in evidence if _observation(ev, "topic_summary")]
    lagging = [
        ev for ev in summaries
        if (ev.payload or {}).get("total_lag") is not None
        and (ev.payload or {}).get("total_lag", 0) > 0
    ]
    metric_lag = [
        ev for ev in evidence
        if (ev.payload or {}).get("metric") == METRIC_KAFKA_CONSUMER_LAG
        and ev.service == incident.service
    ]
    supporting = incident.payload.get("rule_type") == RULE_KAFKA_CONSUMER_LAG
    if not metric_lag and not (lagging and supporting):
        return None
    confidence = 0.85 if supporting else 0.6
    chain = _sorted_chain(metric_lag + lagging)
    topics = sorted({(ev.payload or {}).get("topic") for ev in lagging if (ev.payload or {}).get("topic")})
    return CandidateDraft(
        root_cause_type=RC_KAFKA_LAG,
        title=f"Kafka consumer lag on {', '.join(topics) if topics else 'consumer groups'}",
        summary=(
            f"Live topic summaries show positive lag on {len(lagging)} topic(s) "
            f"and/or metric-level lag records ({len(metric_lag)}); "
            f"incident is kafka-related={supporting}."
        ),
        confidence=confidence,
        evidence=chain,
        related_services=[incident.service, "kafka"],
    )


def rule_database_contention(incident: Incident, evidence: list[Evidence]) -> CandidateDraft | None:
    dbstats = [ev for ev in evidence if _observation(ev, "database_stats")]
    connections = [ev for ev in evidence if _observation(ev, "active_connections")]
    unhealthy = False
    for ev in dbstats:
        payload = ev.payload or {}
        if (payload.get("deadlocks") or 0) > 0:
            unhealthy = True
        commits = payload.get("xact_commit") or 0
        rollbacks = payload.get("xact_rollback") or 0
        total = commits + rollbacks
        if total and (rollbacks / total) > 0.05:
            unhealthy = True
    if not unhealthy:
        return None
    chain = _sorted_chain(dbstats + connections)
    return CandidateDraft(
        root_cause_type=RC_DATABASE_CONTENTION,
        title=f"PostgreSQL contention for {incident.service}",
        summary="PostgreSQL stats show deadlocks and/or an elevated rollback ratio.",
        confidence=0.65,
        evidence=chain,
        related_services=[incident.service, "postgres"],
    )


def rule_error_burst(incident: Incident, evidence: list[Evidence]) -> CandidateDraft | None:
    errors = [
        ev for ev in evidence
        if ev.service == incident.service and _is_error_log(ev)
    ]
    if len(errors) < 5:
        return None
    confidence = min(0.9, 0.5 + 0.05 * len(errors))
    return CandidateDraft(
        root_cause_type=RC_ERROR_BURST,
        title=f"Error burst on {incident.service}",
        summary=f"{len(errors)} ERROR log records for {incident.service} in the investigation window.",
        confidence=round(confidence, 3),
        evidence=_sorted_chain(errors),
        related_services=[incident.service],
    )


def run_correlation(incident: Incident, evidence: list[Evidence], window: timedelta) -> list[CandidateDraft]:
    """Evaluate every deterministic rule and return ranked candidate drafts."""
    rules = [
        rule_deployment_change(incident, evidence, window),
        rule_dependency_failure(incident, evidence),
        rule_redis_pressure(incident, evidence),
        rule_kafka_lag(incident, evidence),
        rule_database_contention(incident, evidence),
        rule_error_burst(incident, evidence),
    ]
    candidates = [rule for rule in rules if rule is not None]
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    return candidates
