"""Orders service: orchestrates checkout and charges via payments."""

from __future__ import annotations

import asyncio
import logging
import os
import uuid

from fastapi import FastAPI
from pydantic import BaseModel

from app.config import DEFAULT_PORTS, Settings
from app.services.common import create_service_app, http_client, jitter_ms, url

log = logging.getLogger("simulator.orders")

SERVICE = "orders"

_orders: dict[str, dict] = {}


class OrderCreate(BaseModel):
    items: list[dict]
    amount: int


def create_app() -> FastAPI:
    settings = Settings()
    app = create_service_app(SERVICE, "Orders Service")

    @app.post("/orders")
    async def create_order(body: OrderCreate):
        await asyncio.sleep(jitter_ms(6) / 1000)
        order_id = uuid.uuid4().hex[:12]
        async with http_client() as client:
            resp = await client.post(
                url(settings.payments_url, "/charge"),
                json={"order_id": order_id, "amount": body.amount},
            )
        payment = resp.json()
        order = {
            "order_id": order_id,
            "items": body.items,
            "amount": body.amount,
            "payment": payment,
        }
        _orders[order_id] = order
        return order

    @app.get("/orders/{order_id}")
    async def get_order(order_id: str):
        return _orders.get(order_id, {"order_id": order_id, "status": "not_found"})

    return app


def main() -> None:
    import uvicorn

    port = int(os.getenv("SIM_SERVICE_PORT", str(DEFAULT_PORTS[SERVICE])))
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
