"""Gateway service: entry point that fans out to auth, orders, inventory."""

from __future__ import annotations

import asyncio
import logging
import os

from fastapi import FastAPI, Header

from app.config import DEFAULT_PORTS, Settings
from app.services.common import create_service_app, http_client, jitter_ms, url

log = logging.getLogger("simulator.gateway")

SERVICE = "gateway"


def create_app() -> FastAPI:
    settings = Settings()
    app = create_service_app(SERVICE, "Gateway Service")

    @app.post("/api/orders/checkout")
    async def checkout(body: dict, authorization: str = Header(default="Bearer dev-token")):
        await asyncio.sleep(jitter_ms(5) / 1000)
        async with http_client() as client:
            auth_resp = await client.post(
                url(settings.auth_url, "/validate"), headers={"Authorization": authorization}
            )
            auth = auth_resp.json()
            order_resp = await client.post(
                url(settings.orders_url, "/orders"),
                json={"items": body.get("items", []), "amount": body.get("amount", 100)},
            )
            order = order_resp.json()
        return {"user": auth, "order": order}

    @app.get("/api/orders/{order_id}")
    async def get_order(order_id: str):
        async with http_client() as client:
            resp = await client.get(url(settings.orders_url, f"/orders/{order_id}"))
        return resp.json()

    @app.get("/api/inventory/{sku}")
    async def get_inventory(sku: str):
        async with http_client() as client:
            resp = await client.get(url(settings.inventory_url, f"/inventory/{sku}"))
        return resp.json()

    return app


def main() -> None:
    import uvicorn

    port = int(os.getenv("SIM_SERVICE_PORT", str(DEFAULT_PORTS[SERVICE])))
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
