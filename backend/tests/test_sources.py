from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.sources.contract import CollectionContext, EvidenceRecord, EvidenceSource
from app.sources.registry import _STORE_BACKED, close_source, create_source
from app.sources.telemetry import LiveTelemetrySource


class _FakeSettings:
    demo_database_url = "postgresql+psycopg://u:p@localhost:1/db"
    demo_redis_url = "redis://localhost:1/0"
    demo_kafka_bootstrap_servers = "localhost:1"


def test_store_backed_maps_to_telemetry_source():
    for step in sorted(_STORE_BACKED):
        source = create_source(step, AsyncMock())
        assert isinstance(source, LiveTelemetrySource)


@pytest.mark.parametrize(
    ("step", "expected_cls"),
    [
        ("database", "LivePostgresSource"),
        ("redis", "LiveRedisSource"),
        ("kafka", "LiveKafkaSource"),
    ],
)
def test_live_sources_map_to_connectors(monkeypatch, step, expected_cls):
    monkeypatch.setattr("app.sources.registry.settings", _FakeSettings())
    source = create_source(step, AsyncMock())
    assert type(source).__name__ == expected_cls


def test_unknown_step_raises():
    with pytest.raises(ValueError):
        create_source("unknown", AsyncMock())


def test_evidence_record_defaults():
    record = EvidenceRecord(
        source="redis",
        service="redis",
        signal="observation",
        timestamp=datetime.now(timezone.utc),
    )
    assert record.payload == {}
    assert record.severity is None
    assert record.evidence_id is None


def test_close_source_awaits_async_close():
    class AsyncCloser:
        async def close(self):
            self.closed = True

    closer = AsyncCloser()
    assert asyncio_run(close_source(closer)) is None


def test_collection_context_defaults_to_utc_now():
    context = CollectionContext(
        incident_id="i",
        investigation_id="inv",
        service="svc",
        window_start=datetime.now(timezone.utc),
    )
    assert context.limit == 500
    assert context.window_end.tzinfo is not None


def asyncio_run(coro):
    import asyncio

    return asyncio.run(coro)
