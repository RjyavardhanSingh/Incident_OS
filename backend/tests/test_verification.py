from datetime import datetime, timedelta, timezone

from app.correlation.rules import (
    RC_DATABASE_CONTENTION,
    RC_DEPENDENCY_FAILURE,
    RC_DEPLOYMENT_CHANGE,
    RC_ERROR_BURST,
    RC_KAFKA_LAG,
    RC_REDIS_PRESSURE,
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
from app.verification.checks import (
    aggregate_status,
    check_deployment_change,
    check_dependency_failure,
    check_error_burst,
    check_kafka_lag,
    check_redis_pressure,
    evaluate_candidate,
)

T0 = datetime(2026, 8, 9, 3, 15, 0, tzinfo=timezone.utc)


def _incident(rule_type: str = "redis_error_rate") -> Incident:
    return Incident(
        service="payments",
        started_at=T0,
        detected_at=T0 + timedelta(minutes=5),
        payload={"rule_type": rule_type},
    )


def _ev(source, service="payments", signal="log", severity=None, payload=None, ts=None):
    return Evidence(
        source=source,
        service=service,
        signal=signal,
        severity=severity,
        timestamp=ts or T0,
        payload=payload or {},
    )


def test_aggregate_status_rules():
    assert aggregate_status([CHECK_PASS]) == VERIFICATION_VERIFIED
    assert aggregate_status([CHECK_SUPPORTING, CHECK_MISSING]) == VERIFICATION_UNVERIFIED
    assert aggregate_status([CHECK_PASS, CHECK_FAIL]) == VERIFICATION_CONTRADICTED
    assert aggregate_status([]) == VERIFICATION_UNVERIFIED


def test_error_burst_verified():
    evidence = [_ev("otel", severity="ERROR", payload={"body": f"err {i}"}, ts=T0) for i in range(8)]
    status, checks = evaluate_candidate(RC_ERROR_BURST, _incident(), evidence)
    assert status == VERIFICATION_VERIFIED
    outcomes = {c["outcome"] for c in checks}
    assert CHECK_PASS in outcomes


def test_error_burst_contradicted_when_no_errors():
    evidence = [_ev("otel", severity="INFO", payload={"body": "ok"})]
    status, _ = evaluate_candidate(RC_ERROR_BURST, _incident(), evidence)
    assert status == VERIFICATION_CONTRADICTED


def test_redis_pressure_verified():
    evidence = [
        _ev("otel", severity="ERROR", payload={"body": "redis timeout"}, ts=T0),
        _ev("redis", signal="observation", payload={"observation": "clients", "connected_clients": 42}, ts=T0),
    ]
    status, _ = evaluate_candidate(RC_REDIS_PRESSURE, _incident(), evidence)
    assert status == VERIFICATION_VERIFIED


def test_kafka_lag_verified_and_contradicted():
    incident = _incident(rule_type="kafka_consumer_lag")
    lagging = [_ev("kafka", signal="observation", payload={"observation": "topic_summary", "total_lag": 9000}, ts=T0)]
    status, _ = evaluate_candidate(RC_KAFKA_LAG, incident, lagging)
    assert status == VERIFICATION_VERIFIED

    no_lag = [_ev("kafka", signal="observation", payload={"observation": "topic_summary", "total_lag": 0}, ts=T0)]
    status, _ = evaluate_candidate(RC_KAFKA_LAG, incident, no_lag)
    assert status == VERIFICATION_CONTRADICTED


def test_database_contention_healthy_contradicts():
    healthy = [_ev("postgres", signal="observation", payload={"observation": "database_stats", "deadlocks": 0, "xact_commit": 100, "xact_rollback": 1}, ts=T0)]
    status, _ = evaluate_candidate(RC_DATABASE_CONTENTION, _incident(), healthy)
    assert status == VERIFICATION_CONTRADICTED

    unhealthy = [_ev("postgres", signal="observation", payload={"observation": "database_stats", "deadlocks": 2, "xact_commit": 100, "xact_rollback": 1}, ts=T0)]
    status, _ = evaluate_candidate(RC_DATABASE_CONTENTION, _incident(), unhealthy)
    assert status == VERIFICATION_VERIFIED


def test_deployment_change_contradicted_without_deployment():
    evidence = [_ev("otel", severity="ERROR", payload={"body": "boom"}, ts=T0)]
    status, checks = evaluate_candidate(RC_DEPLOYMENT_CHANGE, _incident(), evidence)
    assert status == VERIFICATION_CONTRADICTED
    assert any(c["outcome"] == CHECK_FAIL for c in checks)


def test_dependency_failure_verified_with_dependent_errors():
    evidence = [
        _ev("otel", service="gateway", severity="ERROR", payload={"body": "upstream fail"}, ts=T0),
        _ev("otel", service="auth", severity="ERROR", payload={"body": "timeout"}, ts=T0),
    ]
    status, _ = evaluate_candidate(RC_DEPENDENCY_FAILURE, _incident(), evidence)
    assert status == VERIFICATION_VERIFIED


def test_unknown_candidate_type_unverified():
    status, checks = evaluate_candidate("mystery", _incident(), [])
    assert status == VERIFICATION_UNVERIFIED
    assert checks == []
