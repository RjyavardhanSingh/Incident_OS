import logging
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.sources.contract import SIGNAL_OBSERVATION, CollectionContext, EvidenceRecord

logger = logging.getLogger(__name__)

_SERVICES = ("inventory-service", "payments-service")


class LivePostgresSource:
    """Read-only probes against the demo PostgreSQL (schemas demo.inventory / demo.payments).

    Only SELECT statements are issued; a dedicated engine is used so connector
    reads never share or interfere with the backend's write pool.
    """

    def __init__(self, url: str) -> None:
        connect_args = {"options": "-c default_transaction_read_only=on"}
        self._engine: AsyncEngine = create_async_engine(url, connect_args=connect_args)

    async def close(self) -> None:
        await self._engine.dispose()

    async def collect(self, context: CollectionContext) -> list[EvidenceRecord]:
        now = datetime.now(timezone.utc)
        records: list[EvidenceRecord] = []
        try:
            async with self._engine.connect() as conn:
                connections = await conn.execute(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE datname = current_database()"
                    )
                )
                conn_count = connections.scalar_one()
                records.append(
                    EvidenceRecord(
                        source="postgres",
                        service="postgres",
                        signal=SIGNAL_OBSERVATION,
                        timestamp=now,
                        payload={
                            "observation": "active_connections",
                            "database": "incident_os_dev",
                            "value": conn_count,
                        },
                    )
                )

                tables = await conn.execute(
                    text(
                        "SELECT relname, n_live_tup, n_dead_tup FROM pg_stat_user_tables "
                        "WHERE schemaname = 'demo' ORDER BY relname"
                    )
                )
                for relname, live, dead in tables.all():
                    records.append(
                        EvidenceRecord(
                            source="postgres",
                            service="postgres",
                            signal=SIGNAL_OBSERVATION,
                            timestamp=now,
                            payload={
                                "observation": "table_rows",
                                "schema": "demo",
                                "table": relname,
                                "n_live_tup": live,
                                "n_dead_tup": dead,
                            },
                        )
                    )

                dbstats = await conn.execute(
                    text(
                        "SELECT xact_commit, xact_rollback, deadlocks, blks_read, "
                        "blks_hit FROM pg_stat_database WHERE datname = current_database()"
                    )
                )
                row = dbstats.one()
                records.append(
                    EvidenceRecord(
                        source="postgres",
                        service="postgres",
                        signal=SIGNAL_OBSERVATION,
                        timestamp=now,
                        payload={
                            "observation": "database_stats",
                            "xact_commit": row.xact_commit,
                            "xact_rollback": row.xact_rollback,
                            "deadlocks": row.deadlocks,
                            "blks_read": row.blks_read,
                            "blks_hit": row.blks_hit,
                        },
                    )
                )
        except Exception:
            logger.exception("LivePostgresSource collection failed")
            records.append(
                EvidenceRecord(
                    source="postgres",
                    service="postgres",
                    signal=SIGNAL_OBSERVATION,
                    timestamp=datetime.now(timezone.utc),
                    severity="error",
                    payload={"observation": "probe_failed", "error": "connection_error"},
                )
            )
        return records
