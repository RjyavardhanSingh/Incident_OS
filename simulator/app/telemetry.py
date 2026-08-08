from __future__ import annotations

import logging
import threading

from opentelemetry import _logs, metrics, trace
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_lock = threading.Lock()
_initialized = False


def init_telemetry(service_name: str, endpoint: str, protocol: str = "http/protobuf") -> None:
    """Initialize OpenTelemetry providers for the given service.

    Endpoint is the base OTLP/HTTP endpoint; per-signal paths are appended
    by the exporters when configured through the environment. We pass
    per-signal URLs explicitly (the SDK uses an explicit endpoint verbatim).
    """
    global _initialized
    with _lock:
        if _initialized:
            return
        resource = Resource.create({SERVICE_NAME: service_name})

        trace_provider = TracerProvider(resource=resource)
        trace_provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces"))
        )
        trace.set_tracer_provider(trace_provider)

        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics"),
            export_interval_millis=5000,
        )
        metrics.set_meter_provider(
            MeterProvider(resource=resource, metric_readers=[reader])
        )

        logger_provider = LoggerProvider(resource=resource)
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=f"{endpoint}/v1/logs"))
        )
        _logs.set_logger_provider(logger_provider)
        handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        _initialized = True


def instrument_app(app, engine=None) -> None:
    FastAPIInstrumentor.instrument_app(app)
    HTTPXClientInstrumentor().instrument()
    if engine is not None:
        SQLAlchemyInstrumentor().instrument(engine=engine)


def get_tracer(service_name: str) -> trace.Tracer:
    return trace.get_tracer(f"simulator.{service_name}")


def get_meter(service_name: str) -> metrics.Meter:
    return metrics.get_meter(f"simulator.{service_name}")
