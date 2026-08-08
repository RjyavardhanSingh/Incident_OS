import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

INCIDENT_STATUS_OPEN = "OPEN"
INCIDENT_STATUS_RESOLVED = "RESOLVED"

INCIDENT_SEVERITY_CRITICAL = "critical"
INCIDENT_SEVERITY_MAJOR = "major"
INCIDENT_SEVERITY_MINOR = "minor"


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    service: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=INCIDENT_STATUS_OPEN)
    detection_rule_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    detection_rule_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class DetectionRule(Base):
    __tablename__ = "detection_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    rule_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_service: Mapped[str | None] = mapped_column(String(128), nullable=True)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    window_seconds: Mapped[int] = mapped_column(nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
