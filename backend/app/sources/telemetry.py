import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence import Evidence
from app.sources.contract import (
    SIGNAL_LOG,
    SIGNAL_METRIC,
    SIGNAL_TRACE,
    CollectionContext,
    EvidenceRecord,
)

logger = logging.getLogger(__name__)


class LiveTelemetrySource:
    """Collects already-ingested telemetry from the Evidence Store.

    This is the store-backed source for logs/metrics/traces/deployment. Returned
    records reference existing Evidence rows via ``evidence_id`` so the worker
    links them to the investigation instead of duplicating them.
    """

    _SIGNALS = {
        "logs": SIGNAL_LOG,
        "metrics": SIGNAL_METRIC,
        "traces": SIGNAL_TRACE,
    }

    def __init__(self, session: AsyncSession, step_type: str) -> None:
        self._session = session
        self._step_type = step_type

    async def collect(self, context: CollectionContext) -> list[EvidenceRecord]:
        stmt = select(Evidence).limit(context.limit)
        if self._step_type == "deployment":
            stmt = stmt.where(
                Evidence.service == context.service,
                Evidence.payload["attributes"]["source_type"].astext == "deployment",
            )
        elif self._step_type in self._SIGNALS:
            stmt = stmt.where(
                Evidence.service == context.service,
                Evidence.signal == self._SIGNALS[self._step_type],
            )
        else:
            logger.warning("unsupported telemetry step_type=%s", self._step_type)
            return []
        stmt = stmt.where(Evidence.timestamp >= context.window_start)
        stmt = stmt.order_by(Evidence.timestamp.desc())

        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())
        return [
            EvidenceRecord(
                source=row.source,
                service=row.service,
                signal=row.signal,
                timestamp=row.timestamp,
                severity=row.severity,
                trace_id=row.trace_id,
                span_id=row.span_id,
                payload=row.payload or {},
                evidence_id=row.id,
            )
            for row in rows
        ]
