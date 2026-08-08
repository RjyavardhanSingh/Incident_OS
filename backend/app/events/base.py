import uuid
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


class EventEnvelope(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    incident_id: uuid.UUID | None = None
    investigation_id: uuid.UUID | None = None
    producer: str
    schema_version: int = SCHEMA_VERSION
    payload: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class EventPublisher(Protocol):
    def publish(self, envelope: EventEnvelope) -> None: ...


@runtime_checkable
class EventConsumer(Protocol):
    def start(self, on_message) -> None: ...

    def close(self) -> None: ...
