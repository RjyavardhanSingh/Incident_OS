import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

INVESTIGATION_STATUS_CREATED = "CREATED"
INVESTIGATION_STATUS_COLLECTING = "COLLECTING"
INVESTIGATION_STATUS_ANALYZING = "ANALYZING"
INVESTIGATION_STATUS_VERIFYING = "VERIFYING"
INVESTIGATION_STATUS_READY = "READY"
INVESTIGATION_STATUS_FAILED = "FAILED"

STEP_STATUS_PENDING = "PENDING"
STEP_STATUS_RUNNING = "RUNNING"
STEP_STATUS_COMPLETED = "COMPLETED"
STEP_STATUS_FAILED = "FAILED"

COLLECTION_STEPS = [
    "logs",
    "metrics",
    "traces",
    "database",
    "redis",
    "kafka",
    "deployment",
]

STEP_TOPIC_MAP = {
    "logs": "evidence.logs.requested",
    "metrics": "evidence.metrics.requested",
    "traces": "evidence.traces.requested",
    "database": "evidence.database.requested",
    "redis": "evidence.redis.requested",
    "kafka": "evidence.kafka.requested",
    "deployment": "evidence.deployment.requested",
}


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=INVESTIGATION_STATUS_CREATED
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class InvestigationStep(Base):
    __tablename__ = "investigation_steps"
    __table_args__ = (UniqueConstraint("investigation_id", "step_type", name="uq_step_type"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=STEP_STATUS_PENDING, index=True
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
