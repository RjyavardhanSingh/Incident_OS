import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

CORRELATION_RUN_STATUS_RUNNING = "RUNNING"
CORRELATION_RUN_STATUS_COMPLETED = "COMPLETED"
CORRELATION_RUN_STATUS_FAILED = "FAILED"

CANDIDATE_STATUS_PENDING = "PENDING"
CANDIDATE_STATUS_ACCEPTED = "ACCEPTED"
CANDIDATE_STATUS_REJECTED = "REJECTED"


class CorrelationRun(Base):
    """One deterministic correlation pass over an investigation's evidence."""

    __tablename__ = "correlation_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CORRELATION_RUN_STATUS_RUNNING
    )
    failed_sources: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list
    )
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RootCauseCandidate(Base):
    """A deterministic candidate root cause with its evidence chain."""

    __tablename__ = "root_cause_candidates"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("correlation_runs.id", ondelete="CASCADE"), nullable=True
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    root_cause_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str] = mapped_column(String(1024), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=CANDIDATE_STATUS_PENDING
    )
    evidence_chain: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    related_services: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
