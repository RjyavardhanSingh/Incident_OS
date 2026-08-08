"""Factory mapping a step type to its EvidenceSource.

Phase 3 sources:
  - logs/metrics/traces/deployment: LiveTelemetrySource (store-backed).
  - database:   LivePostgresSource (read-only demo PG probes).
  - redis:      LiveRedisSource (read-only probes).
  - kafka:      LiveKafkaSource (topics + consumer lag).

Fixtures (Phase 9 replay) will share this registry keyed by the same step types.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.sources.contract import EvidenceSource
from app.sources.kafka import LiveKafkaSource
from app.sources.postgres import LivePostgresSource
from app.sources.redis_source import LiveRedisSource
from app.sources.telemetry import LiveTelemetrySource

logger = logging.getLogger(__name__)

_STORE_BACKED = {"logs", "metrics", "traces", "deployment"}


def create_source(step_type: str, session: AsyncSession) -> EvidenceSource:
    if step_type in _STORE_BACKED:
        return LiveTelemetrySource(session, step_type)
    if step_type == "database":
        return LivePostgresSource(settings.demo_database_url)
    if step_type == "redis":
        return LiveRedisSource(settings.demo_redis_url)
    if step_type == "kafka":
        return LiveKafkaSource(settings.demo_kafka_bootstrap_servers)
    raise ValueError(f"no EvidenceSource for step_type={step_type}")


async def close_source(source: EvidenceSource) -> None:
    closer = getattr(source, "close", None)
    if closer is not None:
        result = closer()
        if hasattr(result, "__await__"):
            await result
