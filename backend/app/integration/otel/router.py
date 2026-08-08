import time
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.detection import service as detection_service
from app.integration.otel import normalize
from app.models.evidence import Evidence

router = APIRouter(prefix="/api/v1/otlp/v1", tags=["telemetry"])

_SUPPORTED_CONTENT_TYPES = {"application/json", "application/x-protobuf"}

_EVALUATE_INTERVAL_S = 5.0
_last_evaluate_at: float = 0.0

_NORMALIZERS = {
    "logs": normalize.normalize_logs,
    "metrics": normalize.normalize_metrics,
    "traces": normalize.normalize_traces,
}


async def _ingest(signal: str, request: Request, session: AsyncSession):
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in _SUPPORTED_CONTENT_TYPES:
        return JSONResponse(
            status_code=415,
            content={"message": "only application/json or application/x-protobuf OTLP payloads are supported"},
        )
    body = await request.body()
    if not body:
        return JSONResponse(status_code=400, content={"message": "empty body"})
    try:
        records = _NORMALIZERS[signal](body, is_protobuf=content_type == "application/x-protobuf")
    except Exception as exc:
        return JSONResponse(
            status_code=400,
            content={"message": "invalid OTLP payload", "detail": str(exc)},
        )

    collector_run_id = uuid.uuid4().hex
    if records:
        for record in records:
            record["source"] = "otel"
            record["collector_run_id"] = collector_run_id
        session.add_all([Evidence(**record) for record in records])
        await session.commit()

    global _last_evaluate_at
    now = time.monotonic()
    if now - _last_evaluate_at >= _EVALUATE_INTERVAL_S:
        await detection_service.evaluate(session)
        _last_evaluate_at = now
    return {}


@router.post("/logs")
async def ingest_logs(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return await _ingest("logs", request, session)


@router.post("/metrics")
async def ingest_metrics(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return await _ingest("metrics", request, session)


@router.post("/traces")
async def ingest_traces(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    return await _ingest("traces", request, session)
