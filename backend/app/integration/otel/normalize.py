from datetime import datetime, timezone

from google.protobuf.json_format import Parse
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import (
    ExportMetricsServiceRequest,
)
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
)

SIGNAL_LOG = "log"
SIGNAL_METRIC = "metric"
SIGNAL_TRACE = "trace"


def _ts(ns: int) -> datetime:
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc)


def _load_request(body: bytes, message, is_protobuf: bool):
    if is_protobuf:
        message.ParseFromString(body)
    else:
        Parse(body, message)
    return message


def _any_value(value) -> object:
    if value is None:
        return None
    if value.HasField("string_value"):
        return value.string_value
    if value.HasField("int_value"):
        return value.int_value
    if value.HasField("double_value"):
        return value.double_value
    if value.HasField("bool_value"):
        return value.bool_value
    if value.HasField("bytes_value"):
        return value.bytes_value.hex()
    if value.HasField("array_value"):
        return [_any_value(v) for v in value.array_value.values]
    if value.HasField("kvlist_value"):
        return {kv.key: _any_value(kv.value) for kv in value.kvlist_value.values}
    return None


def _attrs(kvlist) -> dict[str, object]:
    return {kv.key: _any_value(kv.value) for kv in kvlist}


def _resource_attrs(resource) -> dict[str, object]:
    if resource is None:
        return {}
    return _attrs(resource.attributes)


def _service(resource_attrs: dict) -> str:
    name = resource_attrs.get("service.name")
    return name if isinstance(name, str) and name else "unknown"


def _hex(b: bytes) -> str | None:
    return b.hex() if b else None


def normalize_logs(body: bytes, is_protobuf: bool) -> list[dict]:
    request = _load_request(body, ExportLogsServiceRequest(), is_protobuf)
    records: list[dict] = []
    for resource_logs in request.resource_logs:
        resource_attrs = _resource_attrs(resource_logs.resource)
        service = _service(resource_attrs)
        for scope_logs in resource_logs.scope_logs:
            for record in scope_logs.log_records:
                timestamp = record.time_unix_nano or record.observed_time_unix_nano
                trace_id = _hex(record.trace_id)
                span_id = _hex(record.span_id)
                severity = record.severity_text or None
                if not severity and record.severity_number:
                    severity = f"SEVERITY_{record.severity_number}"
                records.append(
                    {
                        "signal": SIGNAL_LOG,
                        "service": service,
                        "timestamp": _ts(timestamp),
                        "severity": severity,
                        "trace_id": trace_id,
                        "span_id": span_id,
                        "payload": {
                            "body": _any_value(record.body) if record.HasField("body") else None,
                            "severity_number": record.severity_number,
                            "attributes": _attrs(record.attributes),
                            "resource_attributes": resource_attrs,
                        },
                    }
                )
    return records


def _point_value(point) -> float | int | None:
    fields = point.DESCRIPTOR.fields_by_name
    for field in ("as_double", "as_int"):
        if field in fields and point.HasField(field):
            return getattr(point, field)
    return None


def _metric_kind(metric) -> str:
    for name in ("gauge", "sum", "histogram", "exponential_histogram", "summary"):
        if metric.HasField(name):
            return name
    return "unknown"


def _metric_points(metric) -> list[dict]:
    if metric.HasField("gauge"):
        points = metric.gauge.data_points
    elif metric.HasField("sum"):
        points = metric.sum.data_points
    elif metric.HasField("histogram"):
        points = metric.histogram.data_points
    elif metric.HasField("summary"):
        points = metric.summary.data_points
    else:
        points = []
    out = []
    for point in points:
        entry = {
            "timestamp": _ts(point.time_unix_nano).isoformat(),
            "attributes": _attrs(point.attributes),
        }
        value = _point_value(point)
        if value is not None:
            entry["value"] = value
        if metric.HasField("histogram"):
            entry["count"] = point.count
            entry["sum"] = point.sum
            entry["bucket_counts"] = list(point.bucket_counts)
            entry["explicit_bounds"] = list(point.explicit_bounds)
        if metric.HasField("summary"):
            entry["count"] = point.count
            entry["sum"] = point.sum
        out.append(entry)
    return out


def normalize_metrics(body: bytes, is_protobuf: bool) -> list[dict]:
    request = _load_request(body, ExportMetricsServiceRequest(), is_protobuf)
    records: list[dict] = []
    for resource_metrics in request.resource_metrics:
        resource_attrs = _resource_attrs(resource_metrics.resource)
        service = _service(resource_attrs)
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                points = _metric_points(metric)
                if not points:
                    continue
                timestamp = points[0]["timestamp"]
                records.append(
                    {
                        "signal": SIGNAL_METRIC,
                        "service": service,
                        "timestamp": timestamp,
                        "severity": None,
                        "trace_id": None,
                        "span_id": None,
                        "payload": {
                            "metric": metric.name,
                            "unit": metric.unit,
                            "kind": _metric_kind(metric),
                            "datapoints": points,
                            "resource_attributes": resource_attrs,
                        },
                    }
                )
    return records


def normalize_traces(body: bytes, is_protobuf: bool) -> list[dict]:
    request = _load_request(body, ExportTraceServiceRequest(), is_protobuf)
    records: list[dict] = []
    for resource_spans in request.resource_spans:
        resource_attrs = _resource_attrs(resource_spans.resource)
        service = _service(resource_attrs)
        for scope_spans in resource_spans.scope_spans:
            for span in scope_spans.spans:
                records.append(
                    {
                        "signal": SIGNAL_TRACE,
                        "service": service,
                        "timestamp": _ts(span.start_time_unix_nano),
                        "severity": None,
                        "trace_id": _hex(span.trace_id),
                        "span_id": _hex(span.span_id),
                        "payload": {
                            "name": span.name,
                            "kind": span.kind,
                            "start_time_unix_nano": span.start_time_unix_nano,
                            "end_time_unix_nano": span.end_time_unix_nano,
                            "parent_span_id": _hex(span.parent_span_id),
                            "status": {
                                "code": span.status.code,
                                "message": span.status.message or None,
                            },
                            "attributes": _attrs(span.attributes),
                            "resource_attributes": resource_attrs,
                        },
                    }
                )
    return records
