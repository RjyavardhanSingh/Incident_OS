"""Internal evidence-source contract.

The investigation engine depends on this interface, never on concrete
infrastructure clients. Live sources (Phase 3) and fixture sources (Phase 9
replay) both return the same normalized evidence contract.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

SIGNAL_LOG = "log"
SIGNAL_METRIC = "metric"
SIGNAL_TRACE = "trace"
SIGNAL_OBSERVATION = "observation"


class EvidenceRecord(BaseModel):
    """Normalized evidence returned by every EvidenceSource."""

    model_config = ConfigDict(from_attributes=True)

    source: str
    service: str
    signal: str
    timestamp: datetime
    severity: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_id: uuid.UUID | None = None


@dataclass
class CollectionContext:
    incident_id: uuid.UUID
    investigation_id: uuid.UUID
    service: str
    window_start: datetime
    window_end: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    limit: int = 500


@runtime_checkable
class EvidenceSource(Protocol):
    async def collect(self, context: CollectionContext) -> list[EvidenceRecord]: ...
