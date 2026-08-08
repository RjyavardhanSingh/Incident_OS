from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.evidence import Evidence
from app.schemas.evidence import EvidenceOut

router = APIRouter(prefix="/api/v1/evidence", tags=["evidence"])


@router.get("", response_model=list[EvidenceOut])
async def list_evidence(
    service: str | None = Query(default=None),
    signal: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(Evidence).order_by(Evidence.timestamp.desc()).limit(limit)
    if service:
        stmt = stmt.where(Evidence.service == service)
    if signal:
        stmt = stmt.where(Evidence.signal == signal)
    result = await session.execute(stmt)
    return result.scalars().all()
