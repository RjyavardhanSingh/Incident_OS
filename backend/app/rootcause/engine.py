"""Deterministic fallback root-cause engine.

Selects the investigation's root cause from the correlation candidates after
verification. Selection is deterministic and never involves the LLM:

1. VERIFIED mode: the highest-ranked candidate whose verification accepted it.
2. FALLBACK mode: when no candidate verified, the highest-ranked candidate
   (best confidence and evidence chain) is selected as a best-effort root
   cause, clearly labeled as unverified.

If no candidate exists, no root cause is produced (nothing is invented).
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.correlation import (
    CANDIDATE_STATUS_ACCEPTED,
    RootCauseCandidate,
)
from app.models.root_cause import (
    ROOT_CAUSE_SELECTION_FALLBACK,
    ROOT_CAUSE_SELECTION_VERIFIED,
    RootCause,
)

logger = logging.getLogger(__name__)

_REASON_VERIFIED = (
    "Highest-ranked candidate with independent checks passing and no "
    "contradicting evidence."
)
_REASON_FALLBACK = (
    "No candidate passed deterministic verification; highest-confidence "
    "candidate selected as an unverified best-effort root cause."
)


def _selection(candidates: list[RootCauseCandidate]) -> tuple[str, RootCauseCandidate, str]:
    """Pick the root cause deterministically.

    Candidates are ordered by rank (correlation already ranks by confidence).
    """
    for candidate in candidates:
        if candidate.status == CANDIDATE_STATUS_ACCEPTED:
            return ROOT_CAUSE_SELECTION_VERIFIED, candidate, _REASON_VERIFIED
    return ROOT_CAUSE_SELECTION_FALLBACK, candidates[0], _REASON_FALLBACK


async def select_for_investigation(
    session: AsyncSession, investigation_id
) -> RootCause | None:
    """Persist and return the deterministic root cause for an investigation.

    Idempotent: a selection already recorded for the investigation is returned
    without recomputation (redelivery-safe).
    """
    existing = (
        await session.execute(
            select(RootCause).where(
                RootCause.investigation_id == investigation_id
            )
        )
    ).scalars().first()
    if existing is not None:
        return existing

    candidates = (
        await session.execute(
            select(RootCauseCandidate)
            .where(RootCauseCandidate.investigation_id == investigation_id)
            .order_by(RootCauseCandidate.rank.asc())
        )
    ).scalars().all()
    if not candidates:
        logger.info("no root cause selected for %s: no correlation candidates", investigation_id)
        return None

    mode, best, reasoning = _selection(list(candidates))
    root_cause = RootCause(
        investigation_id=investigation_id,
        candidate_id=best.id,
        selection_mode=mode,
        root_cause_type=best.root_cause_type,
        title=best.title,
        summary=best.summary,
        confidence=best.confidence,
        evidence_chain=best.evidence_chain,
        related_services=best.related_services,
        reasoning=reasoning,
    )
    session.add(root_cause)
    await session.commit()

    logger.info(
        "root cause for investigation %s: mode=%s type=%s confidence=%.2f",
        investigation_id,
        mode,
        best.root_cause_type,
        best.confidence,
    )
    return root_cause
