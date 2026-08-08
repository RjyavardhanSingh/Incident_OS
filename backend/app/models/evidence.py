import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    service: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    signal: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    severity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    span_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    incident_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    investigation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, nullable=True, index=True
    )
    collector_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
