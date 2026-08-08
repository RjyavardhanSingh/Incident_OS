import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IncidentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    service: str
    severity: str
    status: str
    detection_rule_id: uuid.UUID | None
    detection_rule_name: str | None
    started_at: datetime
    detected_at: datetime
    payload: dict


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=256)
    service: str = Field(min_length=1, max_length=128)
    severity: str = Field(default="minor", pattern="^(critical|major|minor)$")


class DetectionRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    rule_type: str
    target_service: str | None
    threshold: float
    window_seconds: int
    enabled: bool
