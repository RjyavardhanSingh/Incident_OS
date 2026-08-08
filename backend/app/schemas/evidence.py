import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    source: str
    service: str
    signal: str
    timestamp: datetime
    severity: str | None
    trace_id: str | None
    span_id: str | None
    incident_id: uuid.UUID | None
    investigation_id: uuid.UUID | None
    collector_run_id: str | None
    payload: dict
