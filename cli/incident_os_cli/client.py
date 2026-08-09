"""Production integration client.

Plug any of your services into Incident OS with one call. Everything goes
out over standard OpenTelemetry (OTLP over HTTPS); Incident OS only *reads*
your telemetry - it never touches your system, files, or databases.

    from incident_os_cli import client

    incidentos = client.install(service="billing", endpoint=os.environ["INCIDENT_OS_URL"])
    incidentos.http(status_code=502, duration_ms=1230)
    incidentos.kafka_lag(topic="orders", lag=2000)
    incidentos.redis_error("redis connection timeout attempt=1")
"""

import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggingHandler, LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

DEFAULT_URL = os.environ.get(
    "INCIDENT_OS_URL", "https://api-2d4e-8000.prg1.zerops.app"
)

_OTLP_SUFFIX = "/api/v1/otlp"


def _normalize_endpoint(endpoint: str) -> str:
    endpoint = (endpoint or DEFAULT_URL).rstrip("/")
    if not endpoint.endswith("/api/v1/otlp"):
        endpoint += _OTLP_SUFFIX
    return endpoint


class Agent:
    """Handles your service's telemetry for Incident OS."""

    def __init__(self, service: str, endpoint: str):
        self.service = service
        self.endpoint = endpoint
        self._redis_logger = logging.getLogger(f"app.redis")
        self._meter = metrics.get_meter("incident-os-client")
        self._histogram = self._meter.create_histogram(
            "http.server.request.duration", unit="ms"
        )
        self._lag = self._meter.create_gauge("kafka.consumer.lag", unit="messages")
        self._tracer = trace.get_tracer("incident-os-client")

    def http(self, status_code: int, duration_ms: float, method: str = "GET", route: str = None) -> None:
        """Record one HTTP request. Drives the 5xx-rate + p95-latency rule."""
        attrs = {"http.status_code": status_code, "http.method": method}
        if route:
            attrs["http.route"] = route
        self._histogram.record(duration_ms, attrs)

    def kafka_lag(self, topic: str, lag: int) -> None:
        """Report a consumer group's lag for a topic. Drives the kafka rule."""
        self._lag.set(lag, {"topic": topic})

    def redis_error(self, message: str) -> None:
        """Log a redis failure at ERROR. Drives the redis rule."""
        self._redis_logger.error(message)

    def span(self, name: str):
        """Return a span context manager for tracing failures through services."""
        return self._tracer.start_as_current_span(name)

    def trace_error(self, name: str, status_code: int = 500) -> None:
        """Open, fail, and close a span (one-shot trace rule trigger)."""
        with self.span(name) as span:
            span.set_attribute("http.status_code", status_code)
            span.set_status(trace.Status(trace.StatusCode.ERROR, "internal failure"))


def install(service: str, endpoint: str = None, flush_interval_s: float = 5.0) -> Agent:
    """Wire this service up to Incident OS and return an :class:`Agent`.

    Safe to call once at process start. Also works alongside any existing
    OpenTelemetry setup - this configures its own providers and reads
    ``OTEL_EXPORTER_OTLP_ENDPOINT`` like any standard OpenTelemetry app.
    """
    endpoint = _normalize_endpoint(endpoint)
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = endpoint
    os.environ["OTEL_EXPORTER_OTLP_PROTOCOL"] = "http/protobuf"

    resource = Resource.create({"service.name": service})

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(), export_interval_millis=int(flush_interval_s * 1000)
    )
    metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))

    log_provider = LoggerProvider(resource=resource)
    log_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
    handler = LoggingHandler(level=logging.ERROR, logger_provider=log_provider)
    logging.getLogger("app.redis").addHandler(handler)
    logging.getLogger("app.redis").setLevel(logging.ERROR)

    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(trace_provider)

    return Agent(service, endpoint)
