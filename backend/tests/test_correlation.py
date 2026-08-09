from datetime import datetime, timedelta, timezone

from app.correlation.rules import (
    RC_DATABASE_CONTENTION,
    RC_DEPENDENCY_FAILURE,
    RC_DEPLOYMENT_CHANGE,
    RC_ERROR_BURST,
    RC_KAFKA_LAG,
    RC_REDIS_PRESSURE,
    run_correlation,
)
from app.detection.rules import RULE_REDIS_ERROR_RATE
from app.models.evidence import Evidence
from app.models.incident import Incident

T0 = datetime(2026, 8, 9, 3, 15, 0, tzinfo=timezone.utc)


def _incident(rule_type: str = RULE_REDIS_ERROR_RATE) -> Incident:
    return Incident(
        service="payments",
        started_at=T0,
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


def test_deployment_change_rule_with_errors():
    incident = _incident()
    evidence = [
        _ev("otel", payload={"attributes": {"source_type": "deployment"}, "revision": "abc"}, ts=T0 - timedelta(seconds=10)),
        _ev("otel", severity="ERROR", payload={"body": "boom"}, ts=T0),
    ]
    candidates = run_correlation(incident, evidence, timedelta(seconds=300))
    deployment = next(c for c in candidates if c.root_cause_type == RC_DEPLOYMENT_CHANGE)
    assert deployment.confidence == 0.9
    assert len(deployment.evidence) == 2


def test_deployment_rule_ignores_old_deployments():
    incident = _incident()
    evidence = [
        _ev("otel", payload={"attributes": {"source_type": "deployment"}}, ts=T0 - timedelta(hours=2)),
        _ev("otel", severity="ERROR", payload={"body": "boom"}, ts=T0),
    ]
    candidates = run_correlation(incident, evidence, timedelta(seconds=300))
    assert all(c.root_cause_type != RC_DEPLOYMENT_CHANGE for c in candidates)


def test_dependency_failure_rule():
    incident = _incident()
    evidence = [
        _ev("otel", service="gateway", severity="ERROR", payload={"body": "upstream down"}, ts=T0),
        _ev("otel", service="auth", severity="ERROR", payload={"body": "timeout"}, ts=T0),
    ]
    candidates = run_correlation(incident, evidence, timedelta(seconds=300))
    dependency = next(c for c in candidates if c.root_cause_type == RC_DEPENDENCY_FAILURE)
    assert dependency.related_services == ["auth", "gateway"]
    assert dependency.confidence == 0.8


def test_redis_pressure_rule_supports_incident():
    incident = _incident(rule_type=RULE_REDIS_ERROR_RATE)
    evidence = [
        _ev("otel", severity="ERROR", payload={"body": "redis connection refused"}, ts=T0),
        _ev("redis", signal="observation", payload={"observation": "clients", "connected_clients": 42}, ts=T0),
    ]
    candidates = run_correlation(incident, evidence, timedelta(seconds=300))
    redis = next(c for c in candidates if c.root_cause_type == RC_REDIS_PRESSURE)
    assert redis.confidence == 0.8


def test_kafka_lag_rule():
    incident = _incident(rule_type="kafka_consumer_lag")
    evidence = [
        _ev("kafka", signal="observation", payload={"observation": "topic_summary", "topic": "payments.processed", "total_lag": 5000}, ts=T0),
    ]
    candidates = run_correlation(incident, evidence, timedelta(seconds=300))
    kafka = next(c for c in candidates if c.root_cause_type == RC_KAFKA_LAG)
    assert kafka.confidence == 0.85
    assert "payments.processed" in kafka.title


def test_database_contention_rule_deadlocks():
    incident = _incident()
    evidence = [
        _ev("postgres", signal="observation", payload={"observation": "database_stats", "deadlocks": 3, "xact_commit": 100, "xact_rollback": 4}, ts=T0),
    ]
    candidates = run_correlation(incident, evidence, timedelta(seconds=300))
    assert any(c.root_cause_type == RC_DATABASE_CONTENTION for c in candidates)


def test_error_burst_rule_minimum():
    incident = _incident()
    evidence = [_ev("otel", severity="ERROR", payload={"body": f"err {i}"}, ts=T0) for i in range(5)]
    candidates = run_correlation(incident, evidence, timedelta(seconds=300))
    burst = next(c for c in candidates if c.root_cause_type == RC_ERROR_BURST)
    assert len(burst.evidence) == 5


def test_no_candidates_with_empty_evidence():
    incident = _incident()
    assert run_correlation(incident, [], timedelta(seconds=300)) == []


def test_candidates_ranked_by_confidence_desc():
    incident = _incident(rule_type=RULE_REDIS_ERROR_RATE)
    evidence = [
        _ev("redis", signal="observation", payload={"observation": "clients", "connected_clients": 1}, ts=T0),
        _ev("otel", severity="ERROR", payload={"body": "redis down"}, ts=T0),
        _ev("otel", payload={"attributes": {"source_type": "deployment"}}, ts=T0 - timedelta(seconds=5)),
        _ev("otel", severity="ERROR", payload={"body": "boom"}, ts=T0),
        _ev("otel", service="gateway", severity="ERROR", payload={"body": "x"}, ts=T0),
    ]
    candidates = run_correlation(incident, evidence, timedelta(seconds=300))
    confidences = [c.confidence for c in candidates]
    assert confidences == sorted(confidences, reverse=True)
