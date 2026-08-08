"""Auth service: validates bearer tokens."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, Header

from app.config import DEFAULT_PORTS
from app.services.common import create_service_app, jitter_ms

log = logging.getLogger("simulator.auth")

SERVICE = "auth"


def create_app() -> FastAPI:
    app = create_service_app(SERVICE, "Auth Service")
    import asyncio

    @app.post("/validate")
    async def validate(authorization: str = Header(default="")):
        await asyncio.sleep(jitter_ms(4) / 1000)
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            return {"valid": False, "reason": "missing_token"}
        return {"valid": True, "user": f"user-{hash(token) % 1000:03d}"}

    return app


def main() -> None:
    import uvicorn

    port = int(os.getenv("SIM_SERVICE_PORT", str(DEFAULT_PORTS[SERVICE])))
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
