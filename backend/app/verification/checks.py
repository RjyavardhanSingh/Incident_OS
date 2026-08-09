"""Deterministic verification checks.

Every candidate root cause gets a set of evidence checks executed against the
Evidence Store. Each check returns PASS / FAIL / SUPPORTING / MISSING and the
candidate-level outcome is aggregated deterministically:

  - any FAIL                     -> CONTRADICTED
  - any PASS (no FAIL)           -> VERIFIED
  - otherwise                    -> UNVERIFIED

No I/O and no randomness; checks are pure over (incident, evidence) so they are
fully unit-testable.
"""
from datetime import timedelta

from app.correlation.rules import (
    RC_DATABASE_CONTENTION,
    RC_DEPENDENCY_FAILURE,
    RC_DEPLOYMENT_CHANGE,
    RC_ERROR_BURST,
    RC_KAFKA_LAG,
    RC_REDIS_PRESSURE,
    _is_deployment,
    _is_error_log,
    _is_error_metric,
    _is_error_span,
    _observation,
)
from app.detection.rules import (
    METRIC_KAFKA_CONSUMER_LAG,
    RULE_KAFKA_CONSUMER_LAG,
    RULE_REDIS_ERROR_RATE,
)
from app.models.evidence import Evidence
from app.models.incident import Incident

from app.models.verification import (
    CHECK_FAIL,
    CHECK_MISSING,
    CHECK_PASS,
    CHECK_SUPPORTING,
    VERIFICATION_CONTRADICTED,
    VERIFICATION_UNVERIFIED,
    VERIFICATION_VERIFIED,
)

CHECK_WINDOW = timedelta(seconds=300)

PASS_SET = {CHECK_PASS}
FAIL_SET = {CHECK_FAIL}


def _window(incident: Incident) -> tuple:
    return incident.started_at - CHECK_WINDOW, incident.detected_at


def _within(ts, window) -> bool:
    start, end = window
    return start <= ts <= end


def _error_signals(evidence: list[Evidence], service: str) -> list[Evidence]:
    return [
        ev for ev in evidence
        if ev.service == service
        and (_is_error_log(ev) or _is_error_metric(ev) or _is_error_span(ev))
    ]


def aggregate_status(outcomes: list[str]) -> str:
    """Aggregate check outcomes into a candidate-level verification status."""
    if any(outcome in FAIL_SET for outcome in outcomes):
        return VERIFICATION_CONTRADICTED
    if any(outcome in PASS_SET for outcome in outcomes):
        return VERIFICATION_VERIFIED
    return VERIFICATION_UNVERIFIED


def check_error_burst(incident: Incident, evidence: list[Evidence]) -> list[dict]:
    errors = [ev for ev in _error_signals(evidence, incident.service) if _is_error_log(ev)]
    window = _window(incident)
    in_window = [ev for ev in errors if _within(ev.timestamp, window)]
    count = len(errors)
    if count == 0:
        outcome = CHECK_FAIL
    elif count >= 5:
        outcome = CHECK_PASS
    else:
        outcome = CHECK_SUPPORTING
    return [
        {"name": "error_logs_present", "outcome": outcome, "detail": {"count": count}},
        {
            "name": "error_logs_overlap_incident_window",
            "outcome": CHECK_PASS if in_window else CHECK_MISSING,
            "detail": {"overlapping": len(in_window)},
        },
    ]


def check_redis_pressure(incident: Incident, evidence: list[Evidence]) -> list[dict]:
    redis_errors = [
        ev for ev in evidence
        if ev.service == incident.service and _is_error_log(ev)
        and "redis" in str(ev.payload).lower()
    ]
    observations = [
        ev for ev in evidence
        if _observation(ev, "clients")
        or _observation(ev, "server")
        or _observation(ev, "keyspace")
    ]
    related = incident.payload.get("rule_type") == RULE_REDIS_ERROR_RATE
    checks = [
        {
            "name": "redis_error_logs",
            "outcome": CHECK_PASS if redis_errors else CHECK_FAIL,
            "detail": {"count": len(redis_errors)},
        },
        {
            "name": "live_redis_observations",
            "outcome": CHECK_PASS if observations else CHECK_MISSING,
            "detail": {"count": len(observations)},
        },
        {
            "name": "incident_redis_related",
            "outcome": CHECK_SUPPORTING if related else CHECK_MISSING,
            "detail": {"rule_type": incident.payload.get("rule_type")},
        },
    ]
    return checks


def check_kafka_lag(incident: Incident, evidence: list[Evidence]) -> list[dict]:
    summaries = [ev for ev in evidence if _observation(ev, "topic_summary")]
    lagging = [
        ev for ev in summaries
        if (ev.payload or {}).get("total_lag") is not None
        and (ev.payload or {}).get("total_lag", 0) > 0
    ]
    if summaries and not lagging:
        live_outcome = CHECK_FAIL
    elif lagging:
        live_outcome = CHECK_PASS
    else:
        live_outcome = CHECK_MISSING
    metric_lag = [
        ev for ev in evidence
        if (ev.payload or {}).get("metric") == METRIC_KAFKA_CONSUMER_LAG
    ]
    related = incident.payload.get("rule_type") == RULE_KAFKA_CONSUMER_LAG
    return [
        {
            "name": "live_topic_lag",
            "outcome": live_outcome,
            "detail": {"lagging_topics": len(lagging)},
        },
        {
            "name": "kafka_metric_lag",
            "outcome": CHECK_SUPPORTING if metric_lag else CHECK_MISSING,
            "detail": {"count": len(metric_lag)},
        },
        {
            "name": "incident_kafka_related",
            "outcome": CHECK_SUPPORTING if related else CHECK_MISSING,
            "detail": {"rule_type": incident.payload.get("rule_type")},
        },
    ]


def check_database_contention(incident: Incident, evidence: list[Evidence]) -> list[dict]:
    dbstats = [ev for ev in evidence if _observation(ev, "database_stats")]
    unhealthy = False
    healthy = False
    for ev in dbstats:
        payload = ev.payload or {}
        if (payload.get("deadlocks") or 0) > 0:
            unhealthy = True
        commits = payload.get("xact_commit") or 0
        rollbacks = payload.get("xact_rollback") or 0
        total = commits + rollbacks
        if total and (rollbacks / total) > 0.05:
            unhealthy = True
        elif total:
            healthy = True
    if not dbstats:
        stats_outcome = CHECK_MISSING
    elif unhealthy:
        stats_outcome = CHECK_PASS
    else:
        stats_outcome = CHECK_FAIL
    connections = [ev for ev in evidence if _observation(ev, "active_connections")]
    return [
        {
            "name": "database_stats_unhealthy",
            "outcome": stats_outcome,
            "detail": {"observations": len(dbstats), "healthy": healthy},
        },
        {
            "name": "active_connections",
            "outcome": CHECK_SUPPORTING if connections else CHECK_MISSING,
            "detail": {"count": len(connections)},
        },
    ]


def check_deployment_change(incident: Incident, evidence: list[Evidence]) -> list[dict]:
    window = _window(incident)
    deployments = [
        ev for ev in evidence
        if _is_deployment(ev) and _within(ev.timestamp, window)
    ]
    errors = _error_signals(evidence, incident.service)
    return [
        {
            "name": "deployment_in_window",
            "outcome": CHECK_PASS if deployments else CHECK_FAIL,
            "detail": {"count": len(deployments)},
        },
        {
            "name": "errors_after_deployment",
            "outcome": CHECK_PASS if errors else CHECK_SUPPORTING,
            "detail": {"error_signals": len(errors)},
        },
    ]


def check_dependency_failure(incident: Incident, evidence: list[Evidence]) -> list[dict]:
    window = _window(incident)
    dependent_errors = [
        ev for ev in evidence
        if ev.service != incident.service
        and (_is_error_log(ev) or _is_error_metric(ev) or _is_error_span(ev))
    ]
    overlapping = [ev for ev in dependent_errors if _within(ev.timestamp, window)]
    return [
        {
            "name": "dependent_service_errors",
            "outcome": CHECK_PASS if dependent_errors else CHECK_FAIL,
            "detail": {"count": len(dependent_errors)},
        },
        {
            "name": "dependent_errors_overlap_window",
            "outcome": CHECK_PASS if overlapping else CHECK_MISSING,
            "detail": {"overlapping": len(overlapping)},
        },
    ]


CHECKERS = {
    RC_ERROR_BURST: check_error_burst,
    RC_REDIS_PRESSURE: check_redis_pressure,
    RC_KAFKA_LAG: check_kafka_lag,
    RC_DATABASE_CONTENTION: check_database_contention,
    RC_DEPLOYMENT_CHANGE: check_deployment_change,
    RC_DEPENDENCY_FAILURE: check_dependency_failure,
}


def evaluate_candidate(
    root_cause_type: str,
    incident: Incident,
    evidence: list[Evidence],
) -> tuple[str, list[dict]]:
    """Run the checks for a candidate type and return (status, checks)."""
    checker = CHECKERS.get(root_cause_type)
    if checker is None:
        return VERIFICATION_UNVERIFIED, []
    checks = checker(incident, evidence)
    return aggregate_status([c["outcome"] for c in checks]), checks
