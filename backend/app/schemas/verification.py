import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class VerificationResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    run_id: uuid.UUID | None
    candidate_id: uuid.UUID
    status: str
    checks: list[dict[str, Any]]
    created_at: datetime


class VerificationRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    status: str
    candidate_count: int
    verified_count: int
    contradicted_count: int
    unverified_count: int
    created_at: datetime
    updated_at: datetime
