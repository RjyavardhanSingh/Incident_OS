"""Deterministic verification engine.

Runs the per-candidate evidence checks, persists a VerificationRun with its
VerificationResults, and updates each candidate's status to
VERIFIED / CONTRADICTED / UNVERIFIED. No LLM involvement.
"""
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.correlation import (
    CANDIDATE_STATUS_ACCEPTED,
    CANDIDATE_STATUS_REJECTED,
    RootCauseCandidate,
)
from app.models.evidence import Evidence
from app.models.incident import Incident
from app.models.investigation import Investigation
from app.models.verification import (
    VERIFICATION_CONTRADICTED,
    VERIFICATION_RUN_STATUS_COMPLETED,
    VERIFICATION_RUN_STATUS_RUNNING,
    VERIFICATION_UNVERIFIED,
    VERIFICATION_VERIFIED,
    VerificationResult,
    VerificationRun,
)
from app.verification.checks import evaluate_candidate

logger = logging.getLogger(__name__)


def _candidate_status(verification_status: str) -> str:
    if verification_status == VERIFICATION_VERIFIED:
        return CANDIDATE_STATUS_ACCEPTED
    if verification_status == VERIFICATION_CONTRADICTED:
        return CANDIDATE_STATUS_REJECTED
    return verification_status


async def run_for_investigation(
    session: AsyncSession, investigation_id: UUID
) -> tuple[VerificationRun, list[VerificationResult]]:
    """Verify every correlation candidate and persist the run + results."""
    run = VerificationRun(
        investigation_id=investigation_id, status=VERIFICATION_RUN_STATUS_RUNNING
    )
    session.add(run)
    await session.commit()

    investigation = await session.get(Investigation, investigation_id)
    incident = await session.get(Incident, investigation.incident_id)

    candidates = (
        (await session.execute(
            select(RootCauseCandidate)
            .where(RootCauseCandidate.investigation_id == investigation_id)
            .order_by(RootCauseCandidate.rank.asc())
        ))
        .scalars()
        .all()
    )
    evidence = (
        (await session.execute(
            select(Evidence)
            .where(Evidence.investigation_id == investigation_id)
        ))
        .scalars()
        .all()
    )

    results: list[VerificationResult] = []
    for candidate in candidates:
        status, checks = evaluate_candidate(
            candidate.root_cause_type, incident, list(evidence)
        )
        result = VerificationResult(
            investigation_id=investigation_id,
            run_id=run.id,
            candidate_id=candidate.id,
            status=status,
            checks=checks,
        )
        session.add(result)
        results.append(result)
        candidate.status = _candidate_status(status)

    run.status = VERIFICATION_RUN_STATUS_COMPLETED
    run.candidate_count = len(candidates)
    run.verified_count = sum(1 for r in results if r.status == VERIFICATION_VERIFIED)
    run.contradicted_count = sum(1 for r in results if r.status == VERIFICATION_CONTRADICTED)
    run.unverified_count = sum(1 for r in results if r.status == VERIFICATION_UNVERIFIED)
    await session.commit()

    logger.info(
        "verification for investigation %s: %d verified, %d contradicted, %d unverified",
        investigation_id,
        run.verified_count,
        run.contradicted_count,
        run.unverified_count,
    )
    return run, results
