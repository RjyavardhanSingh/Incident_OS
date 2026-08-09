import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.investigation import service as investigation_service
from app.models.correlation import CorrelationRun, RootCauseCandidate
from app.models.evidence import Evidence
from app.models.incident import Incident
from app.models.investigation import Investigation, InvestigationStep
from app.models.root_cause import RootCause
from app.models.verification import VerificationResult, VerificationRun
from app.schemas.correlation import CorrelationRunOut, RootCauseCandidateOut
from app.schemas.evidence import EvidenceOut
from app.schemas.investigation import InvestigationOut, InvestigationStepOut
from app.schemas.root_cause import RootCauseOut
from app.schemas.verification import VerificationResultOut, VerificationRunOut

router = APIRouter(prefix="/api/v1", tags=["investigations"])


async def _investigation_out(session: AsyncSession, investigation: Investigation) -> InvestigationOut:
    steps = await investigation_service.list_steps(session, investigation.id)
    return InvestigationOut(
        id=investigation.id,
        incident_id=investigation.incident_id,
        status=investigation.status,
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
        steps=[
            InvestigationStepOut.model_validate(step)
            for step in steps
        ],
    )


@router.post(
    "/incidents/{incident_id}/investigate",
    response_model=InvestigationOut,
    description="Create an investigation asynchronously and publish evidence collection work.",
)
async def start_investigation(
    incident_id: uuid.UUID,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")

    investigation = await investigation_service.create_investigation(session, incident_id)
    publisher = request.app.state.event_publisher
    try:
        await asyncio.to_thread(
            investigation_service.publish_investigation_events,
            publisher,
            investigation,
            incident,
        )
        publisher.flush()
    except Exception as exc:  # pragma: no cover - resilience path
        raise HTTPException(
            status_code=503,
            detail=f"investigation created but work publication failed: {exc}",
        ) from exc

    await investigation_service.transition_investigation(session, investigation.id, "COLLECTING")
    investigation = await session.get(Investigation, investigation.id)
    return await _investigation_out(session, investigation)


@router.get("/investigations/{investigation_id}", response_model=InvestigationOut)
async def get_investigation(
    investigation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    investigation = await session.get(Investigation, investigation_id)
    if investigation is None:
        raise HTTPException(status_code=404, detail="investigation not found")
    return await _investigation_out(session, investigation)


@router.get("/investigations/{investigation_id}/evidence", response_model=list[EvidenceOut])
async def list_investigation_evidence(
    investigation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Evidence)
        .where(Evidence.investigation_id == investigation_id)
        .order_by(Evidence.timestamp.desc())
    )
    return list(result.scalars().all())


@router.get("/investigations/{investigation_id}/candidates", response_model=list[RootCauseCandidateOut])
async def list_root_cause_candidates(
    investigation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(RootCauseCandidate)
        .where(RootCauseCandidate.investigation_id == investigation_id)
        .order_by(RootCauseCandidate.rank.asc())
    )
    return list(result.scalars().all())


@router.get("/investigations/{investigation_id}/correlation-runs", response_model=list[CorrelationRunOut])
async def list_correlation_runs(
    investigation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(CorrelationRun)
        .where(CorrelationRun.investigation_id == investigation_id)
        .order_by(CorrelationRun.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/investigations/{investigation_id}/verification-results", response_model=list[VerificationResultOut])
async def list_verification_results(
    investigation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(VerificationResult)
        .where(VerificationResult.investigation_id == investigation_id)
        .order_by(VerificationResult.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/investigations/{investigation_id}/verification-runs", response_model=list[VerificationRunOut])
async def list_verification_runs(
    investigation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(VerificationRun)
        .where(VerificationRun.investigation_id == investigation_id)
        .order_by(VerificationRun.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/investigations/{investigation_id}/root-cause", response_model=RootCauseOut)
async def get_root_cause(
    investigation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(RootCause).where(RootCause.investigation_id == investigation_id)
    )
    root_cause = result.scalars().first()
    if root_cause is None:
        raise HTTPException(status_code=404, detail="root cause not selected")
    return root_cause
