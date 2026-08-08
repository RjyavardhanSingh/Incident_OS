import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InvestigationStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    step_type: str
    status: str
    attempt: int
    started_at: datetime | None
    completed_at: datetime | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class InvestigationOut(BaseModel):
    id: uuid.UUID
    incident_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime
    steps: list[InvestigationStepOut]
