from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routes import evidence, health, incidents, investigations
from app.core.db import async_session_factory
from app.detection import service as detection_service
from app.events.kafka import KafkaEventPublisher
from app.integration.otel import router as otel_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with async_session_factory() as session:
        await detection_service.seed_default_rules(session)
    app.state.event_publisher = KafkaEventPublisher()
    yield
    app.state.event_publisher.flush()


app = FastAPI(
    title="Incident OS",
    description="External incident investigation and response platform.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(evidence.router)
app.include_router(incidents.router)
app.include_router(investigations.router)
app.include_router(otel_router.router)
