import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

VERIFICATION_RUN_STATUS_RUNNING = "RUNNING"
VERIFICATION_RUN_STATUS_COMPLETED = "COMPLETED"
VERIFICATION_RUN_STATUS_FAILED = "FAILED"

VERIFICATION_VERIFIED = "VERIFIED"
VERIFICATION_CONTRADICTED = "CONTRADICTED"
VERIFICATION_UNVERIFIED = "UNVERIFIED"

CHECK_PASS = "PASS"
CHECK_FAIL = "FAIL"
CHECK_SUPPORTING = "SUPPORTING"
CHECK_MISSING = "MISSING"


class VerificationRun(Base):
    """One deterministic verification pass over the correlation candidates."""

    __tablename__ = "verification_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=VERIFICATION_RUN_STATUS_RUNNING
    )
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    contradicted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unverified_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class VerificationResult(Base):
    """Per-candidate verification outcome with its individual checks."""

    __tablename__ = "verification_results"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_runs.id", ondelete="CASCADE"), nullable=True
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("root_cause_candidates.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    checks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
