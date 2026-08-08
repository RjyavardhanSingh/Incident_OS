import os
import time

os.environ.setdefault("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:8000/api/v1/otlp")
os.environ.setdefault("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.metrics import get_meter_provider, set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.semconv.trace import SpanAttributes

metrics_resource = Resource.create({"service.name": "gateway"})
logs_resource = Resource.create({"service.name": "billing"})
traces_resource = Resource.create({"service.name": "gateway"})

reader = PeriodicExportingMetricReader(OTLPMetricExporter())
set_meter_provider(MeterProvider(resource=metrics_resource, metric_readers=[reader]))
meter = get_meter_provider().get_meter("fault-simulator")

histogram = meter.create_histogram("http.server.request.duration", unit="ms")
for i in range(7):
    histogram.record(800 + i * 10, {"http.status_code": 500, "http.method": "GET"})
for i in range(3):
    histogram.record(200 + i * 5, {"http.status_code": 200, "http.method": "GET"})

lag = meter.create_gauge("kafka.consumer.lag", unit="messages")
lag.set(2000, {"topic": "orders"})

logger_provider = LoggerProvider(resource=logs_resource)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(OTLPLogExporter()))
import logging
logging.basicConfig(level=logging.ERROR, handlers=[LoggingHandler(level=logging.ERROR, logger_provider=logger_provider)])
for i in range(12):
    logging.error("redis connection timeout attempt=%d", i)

trace.set_tracer_provider(TracerProvider(resource=traces_resource))
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
with trace.get_tracer("fault-simulator").start_as_current_span("checkout") as span:
    span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, 500)
    span.set_status(trace.Status(trace.StatusCode.ERROR, "internal failure"))

reader.force_flush()
logger_provider.force_flush()
trace.get_tracer_provider().force_flush()
time.sleep(1)
print("emitted failure telemetry")
