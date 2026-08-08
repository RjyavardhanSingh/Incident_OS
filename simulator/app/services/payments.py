"""Payments service: Redis cache, PostgreSQL writes, Kafka publishing.

Chaos flags (Redis keys under sim:chaos:payments:*):
  redis_timeout_ms    simulated Redis latency
  redis_failure_rate  0..1 probability of a Redis failure
  payment_failure_rate 0..1 probability of a declined charge
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random

from confluent_kafka import Producer
from fastapi import FastAPI
from pydantic import BaseModel

from app import chaos, db, telemetry
from app import models as db_models
from app.config import DEFAULT_PORTS, Settings
from app.services.common import create_service_app, jitter_ms

log = logging.getLogger("simulator.payments")

SERVICE = "payments"
REDIS_CACHE_KEY = "sim:payments:charge:{}"

_producer: Producer | None = None


def _get_producer(settings: Settings) -> Producer:
    global _producer
    if _producer is None:
        _producer = Producer({"bootstrap.servers": settings.kafka_bootstrap})
    return _producer


def _publish(settings: Settings, event: dict) -> bool:
    try:
        producer = _get_producer(settings)
        producer.produce(
            "payments.processed",
            key=event["payment_id"],
            value=json.dumps(event),
        )
        producer.poll(0)
        producer.flush(1.0)
        return True
    except Exception as exc:  # pragma: no cover - env dependent
        log.error("kafka publish failed: %s", exc)
        return False


def _redis_cache(settings: Settings):
    import redis

    return redis.Redis.from_url(
        settings.redis_url, decode_responses=True, socket_timeout=0.5
    )


def _get_redis_delay(client) -> int:
    return int(chaos.get_flag(SERVICE, "redis_timeout_ms", 50))


class ChargeRequest(BaseModel):
    order_id: str
    amount: int


def create_app() -> FastAPI:
    settings = Settings()
    db.ensure_demo_schema()
    db.create_tables()
    app = create_service_app(SERVICE, "Payments Service")
    telemetry.init_telemetry(SERVICE, settings.otel_endpoint)
    meter = telemetry.get_meter(SERVICE)
    redis_latency_hist = meter.create_histogram("redis.request.duration", unit="ms")
    redis_error_counter = meter.create_counter("redis.request.errors", unit="1")
    charge_hist = meter.create_histogram("payment.charge.duration", unit="ms")

    @app.post("/charge")
    async def charge(body: ChargeRequest):
        started = asyncio.get_running_loop().time()

        cache_key = REDIS_CACHE_KEY.format(body.order_id)
        client = None
        redis_ms = 0.0
        redis_ok = True
        try:
            client = _redis_cache(settings)
            redis_ms = _get_redis_delay(client)
            if redis_ms > 0:
                await asyncio.sleep(redis_ms / 1000)
            if random.random() < chaos.get_flag(SERVICE, "redis_failure_rate", 0.0):
                raise ConnectionError("redis: connection reset by peer (injected)")
            cached = client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception as exc:
            redis_ok = False
            redis_error_counter.add(1)
            redis_latency_hist.record((asyncio.get_running_loop().time() - started) * 1000)
            log.error("redis connection timeout: %s", exc)

        charge_ms = jitter_ms(25)
        await asyncio.sleep(charge_ms / 1000)

        failed = random.random() < chaos.get_flag(SERVICE, "payment_failure_rate", 0.0)
        status = "declined" if failed else "approved"

        payload = {
            "payment_id": f"pay-{body.order_id}",
            "order_id": body.order_id,
            "amount": body.amount,
            "status": status,
            "redis_used": redis_ok,
        }

        if status == "approved":
            try:
                session = db.new_session()
                session.add(
                    db_models.Payment(
                        order_id=body.order_id,
                        amount=body.amount,
                        status=status,
                    )
                )
                session.commit()
                session.close()
            except Exception as exc:  # pragma: no cover - env dependent
                log.error("payment persist failed: %s", exc)
            _publish(settings, payload)

        charge_hist.record((asyncio.get_running_loop().time() - started) * 1000)

        if client is not None and redis_ok:
            try:
                client.setex(cache_key, 120, json.dumps(payload))
            except Exception:
                pass

        return {"status": status, **payload}

    return app


def main() -> None:
    import uvicorn

    port = int(os.getenv("SIM_SERVICE_PORT", str(DEFAULT_PORTS[SERVICE])))
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
