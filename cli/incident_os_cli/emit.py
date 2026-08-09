import logging
import os
import time

PROFILES = ("all", "http", "kafka", "redis", "trace")

_PROFILE_DESCRIPTIONS = {
    "all": "http 5xx + p95 latency metrics, kafka consumer lag, redis error logs, checkout trace",
    "http": "http.server.request.duration histogram (5xx rate + p95 latency)",
    "kafka": "kafka.consumer.lag gauge",
    "redis": "redis connection timeout error logs",
    "trace": "checkout span with HTTP 500",
}


def _configure(otlp_endpoint: str):
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = otlp_endpoint
    os.environ["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"


def _emit_metrics():
    from opentelemetry import metrics
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource

    reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    provider = MeterProvider(
        resource=Resource.create({"service.name": "gateway"}), metric_readers=[reader]
    )
    metrics.set_meter_provider(provider)
    meter = metrics.get_meter_provider().get_meter("incident-os-cli")

    histogram = meter.create_histogram("http.server.request.duration", unit="ms")
    for i in range(7):
        histogram.record(800 + i * 10, {"http.status_code": 500, "http.method": "GET"})
    for i in range(3):
        histogram.record(200 + i * 5, {"http.status_code": 200, "http.method": "GET"})

    lag = meter.create_gauge("kafka.consumer.lag", unit="messages")
    lag.set(2000, {"topic": "orders"})

    reader.force_flush()


def _emit_logs():
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource

    provider = LoggerProvider(resource=Resource.create({"service.name": "billing"}))
    provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    handler = LoggingHandler(level=logging.ERROR, logger_provider=provider)
    logger = logging.getLogger("incident-os-cli.redis")
    logger.handlers = [handler]
    logger.setLevel(logging.ERROR)
    for i in range(12):
        logger.error("redis connection timeout attempt=%d", i)
    provider.force_flush()


def _emit_trace():
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.semconv.trace import SpanAttributes

    provider = TracerProvider(resource=Resource.create({"service.name": "gateway"}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    tracer = trace.get_tracer("fault-simulator")
    with tracer.start_as_current_span("checkout") as span:
        span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 500)
        span.set_status(trace.Status(trace.StatusCode.ERROR, "internal failure"))
    provider.force_flush()


def emit(otlp_endpoint: str, profile: str = "all") -> None:
    if profile not in PROFILES:
        raise ValueError(f"unknown profile {profile!r}, expected one of {PROFILES}")
    _configure(otlp_endpoint)
    if profile in ("all", "http", "kafka"):
        _emit_metrics()
    if profile in ("all", "redis"):
        _emit_logs()
    if profile in ("all", "trace"):
        _emit_trace()
    time.sleep(1)
    print(f"emitted {profile!r} telemetry: {_PROFILE_DESCRIPTIONS[profile]} -> {otlp_endpoint}")
