from dataclasses import dataclass, field
from typing import Any

from app.models.evidence import Evidence

METRIC_HTTP_DURATION = "http.server.request.duration"
METRIC_KAFKA_CONSUMER_LAG = "kafka.consumer.lag"
SIGNAL_METRIC = "metric"
SIGNAL_LOG = "log"

RULE_HTTP_5XX_RATE = "http_5xx_rate"
RULE_P95_LATENCY = "p95_latency"
RULE_REDIS_ERROR_RATE = "redis_error_rate"
RULE_KAFKA_CONSUMER_LAG = "kafka_consumer_lag"
RULE_DEPLOYMENT_REGRESSION = "deployment_regression"


@dataclass
class Violation:
    rule_type: str
    rule_name: str
    service: str
    value: float
    threshold: float
    detail: dict[str, Any] = field(default_factory=dict)


def _percentile(bounds: list[float], counts: list[int], q: float) -> float | None:
    total = sum(counts)
    if total == 0:
        return None
    target = total * q
    cumulative = 0
    for bound, count in zip(bounds, counts[:-1]):
        cumulative += count
        if cumulative >= target:
            return float(bound)
    if bounds:
        return float(bounds[-1])
    return None


def _status_code(dp: dict) -> int | None:
    code = dp.get("attributes", {}).get("http.status_code")
    if code is None:
        code = dp.get("attributes", {}).get("http.response.status_code")
    return code if isinstance(code, (int, float)) else None


def _has_errors(evidence: list[Evidence]) -> bool:
    for ev in evidence:
        payload = ev.payload or {}
        if payload.get("metric") == METRIC_HTTP_DURATION:
            for dp in payload.get("datapoints", []):
                code = _status_code(dp)
                if code is not None and code >= 500:
                    return True
        if ev.signal == SIGNAL_LOG and ev.severity == "ERROR":
            return True
    return False


def eval_http_5xx_rate(evidence: list[Evidence], rule) -> list[Violation]:
    totals: dict[str, int] = {}
    errors: dict[str, int] = {}
    for ev in evidence:
        payload = ev.payload or {}
        if payload.get("metric") != METRIC_HTTP_DURATION:
            continue
        for dp in payload.get("datapoints", []):
            code = _status_code(dp)
            if code is None:
                continue
            count = dp.get("count") or 1
            totals[ev.service] = totals.get(ev.service, 0) + count
            if code >= 500:
                errors[ev.service] = errors.get(ev.service, 0) + count
    violations = []
    for service in totals:
        if totals[service] == 0:
            continue
        rate = errors.get(service, 0) / totals[service]
        if rate >= rule.threshold:
            violations.append(
                Violation(
                    rule_type=RULE_HTTP_5XX_RATE,
                    rule_name=rule.name,
                    service=service,
                    value=round(rate, 4),
                    threshold=rule.threshold,
                    detail={"total": totals[service], "errors": errors.get(service, 0)},
                )
            )
    return violations


def eval_p95_latency(evidence: list[Evidence], rule) -> list[Violation]:
    histograms: dict[str, tuple[list[float], list[int]]] = {}
    for ev in evidence:
        payload = ev.payload or {}
        if payload.get("metric") != METRIC_HTTP_DURATION:
            continue
        for dp in payload.get("datapoints", []):
            bounds = dp.get("explicit_bounds")
            counts = dp.get("bucket_counts")
            if not bounds or not counts:
                continue
            if ev.service not in histograms:
                histograms[ev.service] = (list(bounds), [0] * len(counts))
            existing_bounds, merged = histograms[ev.service]
            for i, count in enumerate(counts):
                merged[i] += count
    violations = []
    for service, (bounds, counts) in histograms.items():
        p95 = _percentile(bounds, counts, 0.95)
        if p95 is not None and p95 >= rule.threshold:
            violations.append(
                Violation(
                    rule_type=RULE_P95_LATENCY,
                    rule_name=rule.name,
                    service=service,
                    value=p95,
                    threshold=rule.threshold,
                    detail={"p95": p95, "samples": sum(counts)},
                )
            )
    return violations


def eval_redis_error_rate(evidence: list[Evidence], rule) -> list[Violation]:
    counts: dict[str, int] = {}
    for ev in evidence:
        if ev.signal != SIGNAL_LOG or ev.severity != "ERROR":
            continue
        blob = str(ev.payload).lower()
        if "redis" not in blob:
            continue
        counts[ev.service] = counts.get(ev.service, 0) + 1
    violations = []
    for service, count in counts.items():
        if count >= rule.threshold:
            violations.append(
                Violation(
                    rule_type=RULE_REDIS_ERROR_RATE,
                    rule_name=rule.name,
                    service=service,
                    value=count,
                    threshold=rule.threshold,
                    detail={"error_logs": count},
                )
            )
    return violations


def eval_kafka_consumer_lag(evidence: list[Evidence], rule) -> list[Violation]:
    lags: dict[str, float] = {}
    for ev in evidence:
        payload = ev.payload or {}
        if payload.get("metric") != METRIC_KAFKA_CONSUMER_LAG:
            continue
        for dp in payload.get("datapoints", []):
            value = dp.get("value")
            if isinstance(value, (int, float)):
                lags[ev.service] = max(lags.get(ev.service, 0.0), float(value))
    violations = []
    for service, lag in lags.items():
        if lag >= rule.threshold:
            violations.append(
                Violation(
                    rule_type=RULE_KAFKA_CONSUMER_LAG,
                    rule_name=rule.name,
                    service=service,
                    value=lag,
                    threshold=rule.threshold,
                    detail={"consumer_lag": lag},
                )
            )
    return violations


def eval_deployment_regression(
    evidence: list[Evidence], rule
) -> list[Violation]:
    deployments = {
        ev.service
        for ev in evidence
        if (ev.payload or {}).get("source_type") == "deployment"
        or (ev.payload or {}).get("attributes", {}).get("source_type") == "deployment"
    }
    violations = []
    for service in deployments:
        service_evidence = [ev for ev in evidence if ev.service == service]
        if not _has_errors(service_evidence):
            continue
        violations.append(
            Violation(
                rule_type=RULE_DEPLOYMENT_REGRESSION,
                rule_name=rule.name,
                service=service,
                value=1.0,
                threshold=rule.threshold,
                detail={"deployment_in_window": True, "errors_observed": True},
            )
        )
    return violations


EVALUATORS = {
    RULE_HTTP_5XX_RATE: eval_http_5xx_rate,
    RULE_P95_LATENCY: eval_p95_latency,
    RULE_REDIS_ERROR_RATE: eval_redis_error_rate,
    RULE_KAFKA_CONSUMER_LAG: eval_kafka_consumer_lag,
    RULE_DEPLOYMENT_REGRESSION: eval_deployment_regression,
}


def evaluate_rule(evidence: list[Evidence], rule) -> list[Violation]:
    evaluator = EVALUATORS.get(rule.rule_type)
    if evaluator is None:
        return []
    return evaluator(evidence, rule)


SEVERITY_BY_RULE = {
    RULE_HTTP_5XX_RATE: "critical",
    RULE_P95_LATENCY: "critical",
    RULE_REDIS_ERROR_RATE: "major",
    RULE_KAFKA_CONSUMER_LAG: "major",
    RULE_DEPLOYMENT_REGRESSION: "critical",
}

DEFAULT_RULES = [
    {
        "name": "http_5xx_rate_high",
        "rule_type": RULE_HTTP_5XX_RATE,
        "threshold": 0.05,
        "window_seconds": 60,
    },
    {
        "name": "p95_latency_high",
        "rule_type": RULE_P95_LATENCY,
        "threshold": 400.0,
        "window_seconds": 60,
    },
    {
        "name": "redis_error_rate_high",
        "rule_type": RULE_REDIS_ERROR_RATE,
        "threshold": 10.0,
        "window_seconds": 60,
    },
    {
        "name": "kafka_consumer_lag_high",
        "rule_type": RULE_KAFKA_CONSUMER_LAG,
        "threshold": 1000.0,
        "window_seconds": 60,
    },
    {
        "name": "deployment_regression",
        "rule_type": RULE_DEPLOYMENT_REGRESSION,
        "threshold": 0.05,
        "window_seconds": 300,
    },
]
