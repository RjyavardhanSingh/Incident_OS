import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.incident import (
    INCIDENT_STATUS_OPEN,
    INCIDENT_STATUS_RESOLVED,
    DetectionRule,
    Incident,
)
from app.schemas.incident import DetectionRuleOut, IncidentCreate, IncidentOut

router = APIRouter(prefix="/api/v1", tags=["incidents"])


@router.get("/incidents", response_model=list[IncidentOut])
async def list_incidents(
    service: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Incident).order_by(Incident.detected_at.desc()).limit(limit)
    if service:
        stmt = stmt.where(Incident.service == service)
    if status:
        stmt = stmt.where(Incident.status == status)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/incidents/{incident_id}", response_model=IncidentOut)
async def get_incident(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    return incident


@router.post(
    "/incidents",
    response_model=IncidentOut,
    description="Development/debugging endpoint. The primary path creates incidents via deterministic detection.",
)
async def create_incident_manual(
    body: IncidentCreate,
    session: AsyncSession = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    incident = Incident(
        title=body.title,
        service=body.service,
        severity=body.severity,
        status="OPEN",
        started_at=now,
        payload={"manual": True},
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return incident


@router.get("/detection/rules", response_model=list[DetectionRuleOut])
async def list_detection_rules(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(DetectionRule).order_by(DetectionRule.name)
    )
    return result.scalars().all()


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=IncidentOut,
    description="Resolves an open incident so its detection rule can fire again on new telemetry.",
)
async def resolve_incident(
    incident_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    incident = await session.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="incident not found")
    if incident.status == INCIDENT_STATUS_RESOLVED:
        raise HTTPException(status_code=409, detail="incident already resolved")
    incident.status = INCIDENT_STATUS_RESOLVED
    incident.payload = {
        **incident.payload,
        "resolved_at": datetime.now(timezone.utc).isoformat(),
    }
    await session.commit()
    await session.refresh(incident)
    return incident
