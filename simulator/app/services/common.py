"""Shared helpers for demo services."""

from __future__ import annotations

import os
import random

from fastapi import FastAPI

from app import telemetry
from app.config import Settings


def create_service_app(service_name: str, title: str) -> FastAPI:
    settings = Settings()
    telemetry.init_telemetry(service_name, settings.otel_endpoint)
    app = FastAPI(title=title)
    telemetry.instrument_app(app)

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": service_name}

    return app


def jitter_ms(mean: int, spread: int = 0) -> int:
    if spread <= 0:
        return mean
    return max(1, mean + random.randint(-spread, spread))


def http_client() -> "httpx.AsyncClient":
    import httpx

    return httpx.AsyncClient(timeout=10.0)


def url(base: str, path: str) -> str:
    return base.rstrip("/") + path
