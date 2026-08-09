import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

ROOT_CAUSE_SELECTION_VERIFIED = "VERIFIED"
ROOT_CAUSE_SELECTION_FALLBACK = "FALLBACK"


class RootCause(Base):
    """The deterministically selected root cause for an investigation.

    ``selection_mode`` records whether the root cause came from a verified
    candidate (VERIFIED) or is the highest-ranked unverified candidate used as
    a best-effort fallback (FALLBACK). Selection never involves the LLM.
    """

    __tablename__ = "root_causes"
    __table_args__ = (
        UniqueConstraint("investigation_id", name="uq_root_cause_investigation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("root_cause_candidates.id", ondelete="SET NULL"), nullable=True
    )
    selection_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    root_cause_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    summary: Mapped[str] = mapped_column(String(1024), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_chain: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    related_services: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    reasoning: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
