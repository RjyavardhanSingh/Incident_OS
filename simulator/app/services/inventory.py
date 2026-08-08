"""Inventory service: reads stock from PostgreSQL with optional DB chaos."""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import FastAPI

from app import chaos, db, telemetry
from app import models as db_models
from app.config import DEFAULT_PORTS, Settings
from app.services.common import create_service_app

log = logging.getLogger("simulator.inventory")

SERVICE = "inventory"


def create_app() -> FastAPI:
    settings = Settings()
    db.ensure_demo_schema()
    db.create_tables()
    app = create_service_app(SERVICE, "Inventory Service")
    telemetry.init_telemetry(SERVICE, settings.otel_endpoint)
    meter = telemetry.get_meter(SERVICE)
    db_hist = meter.create_histogram("inventory.query.duration", unit="ms")

    @app.get("/inventory/{sku}")
    async def get_inventory(sku: str):
        started = asyncio.get_running_loop().time()
        slow_ms = chaos.get_flag(SERVICE, "db_slow_ms", 0.0)
        if slow_ms > 0:
            await asyncio.sleep(slow_ms / 1000)
        fail = random_failure()
        if fail:
            log.error("postgres query failed for sku=%s (injected)", sku)
            db_hist.record((asyncio.get_running_loop().time() - started) * 1000)
            return {"sku": sku, "stock": -1, "error": "database connection lost"}
        session = db.new_session()
        try:
            item = session.get(db_models.InventoryItem, sku)
        finally:
            session.close()
        db_hist.record((asyncio.get_running_loop().time() - started) * 1000)
        if item is None:
            session2 = db.new_session()
            session2.add(db_models.InventoryItem(sku=sku, stock=100))
            session2.commit()
            session2.close()
            return {"sku": sku, "stock": 100}
        return {"sku": sku, "stock": item.stock}

    return app


def random_failure() -> bool:
    import random

    return random.random() < chaos.get_flag(SERVICE, "db_failure_rate", 0.0)


def main() -> None:
    import uvicorn

    port = int(os.getenv("SIM_SERVICE_PORT", str(DEFAULT_PORTS[SERVICE])))
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
