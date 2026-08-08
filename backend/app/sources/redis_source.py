import logging
from datetime import datetime, timezone

import redis.asyncio as aioredis

from app.sources.contract import SIGNAL_OBSERVATION, CollectionContext, EvidenceRecord

logger = logging.getLogger(__name__)


class LiveRedisSource:
    """Read-only probes against the demo Redis (sim:*) keyspace.

    Only INFO / PING / DBSIZE are issued; no keys are written or modified.
    """

    def __init__(self, url: str) -> None:
        self._client: aioredis.Redis = aioredis.from_url(url, decode_responses=True)

    async def close(self) -> None:
        await self._client.aclose()

    async def collect(self, context: CollectionContext) -> list[EvidenceRecord]:
        now = datetime.now(timezone.utc)
        records: list[EvidenceRecord] = []
        try:
            server = await self._client.info("server")
            clients = await self._client.info("clients")
            dbsize = await self._client.dbsize()
            pong = await self._client.ping()

            records.extend(
                [
                    EvidenceRecord(
                        source="redis",
                        service="redis",
                        signal=SIGNAL_OBSERVATION,
                        timestamp=now,
                        payload={
                            "observation": "server",
                            "redis_version": server.get("redis_version"),
                            "uptime_in_seconds": server.get("uptime_in_seconds"),
                        },
                    ),
                    EvidenceRecord(
                        source="redis",
                        service="redis",
                        signal=SIGNAL_OBSERVATION,
                        timestamp=now,
                        payload={
                            "observation": "clients",
                            "connected_clients": clients.get("connected_clients"),
                            "blocked_clients": clients.get("blocked_clients"),
                        },
                    ),
                    EvidenceRecord(
                        source="redis",
                        service="redis",
                        signal=SIGNAL_OBSERVATION,
                        timestamp=now,
                        payload={
                            "observation": "keyspace",
                            "db": "0",
                            "dbsize": dbsize,
                            "ping": pong,
                        },
                    ),
                ]
            )
        except Exception:
            logger.exception("LiveRedisSource collection failed")
            records.append(
                EvidenceRecord(
                    source="redis",
                    service="redis",
                    signal=SIGNAL_OBSERVATION,
                    timestamp=datetime.now(timezone.utc),
                    severity="error",
                    payload={"observation": "probe_failed", "error": "connection_error"},
                )
            )
        return records
