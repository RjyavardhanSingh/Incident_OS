import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RootCauseCandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    run_id: uuid.UUID | None
    rank: int
    root_cause_type: str
    title: str
    summary: str
    confidence: float
    status: str
    evidence_chain: list[dict[str, Any]]
    related_services: list[str]
    created_at: datetime


class CorrelationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    status: str
    failed_sources: list[str]
    candidate_count: int
    created_at: datetime
    updated_at: datetime
