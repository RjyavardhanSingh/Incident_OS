import uuid
from datetime import datetime

from pydantic import BaseModel


class RootCauseOut(BaseModel):
    id: uuid.UUID
    investigation_id: uuid.UUID
    candidate_id: uuid.UUID | None
    selection_mode: str
    root_cause_type: str
    title: str
    summary: str
    confidence: float
    evidence_chain: list
    related_services: list
    reasoning: str
    created_at: datetime

    model_config = {"from_attributes": True}
