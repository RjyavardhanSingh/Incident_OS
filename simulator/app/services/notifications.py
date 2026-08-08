"""Notifications service: consumes payments.processed and reports Kafka lag."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading

from confluent_kafka import Consumer, TopicPartition
from fastapi import FastAPI

from app import chaos, telemetry
from app.config import DEFAULT_PORTS, Settings
from app.services.common import create_service_app

log = logging.getLogger("simulator.notifications")

SERVICE = "notifications"
TOPIC = "payments.processed"

_consumer: Consumer | None = None


def _get_consumer(settings: Settings) -> Consumer:
    global _consumer
    if _consumer is None:
        _consumer = Consumer(
            {
                "bootstrap.servers": settings.kafka_bootstrap,
                "group.id": "notifications",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": True,
            }
        )
        _consumer.subscribe([TOPIC])
    return _consumer


def _report_lag(settings: Settings) -> None:
    meter = telemetry.get_meter(SERVICE)
    gauge = meter.create_gauge("kafka.consumer.lag", unit="messages")
    try:
        consumer = _get_consumer(settings)
        for partition in consumer.assignment():
            low, high = consumer.get_watermark_offsets(partition, timeout=2.0)
            position = consumer.position([partition])[0].offset
            lag = max(0, high - max(position, low))
            gauge.set(lag, {"topic": TOPIC, "partition": partition.partition})
    except Exception as exc:  # pragma: no cover - env dependent
        log.debug("lag report failed: %s", exc)


def _consume_loop(settings: Settings) -> None:
    async def _run() -> None:
        while True:
            try:
                consumer = _get_consumer(settings)
                if chaos.consumer_stopped(SERVICE):
                    _report_lag(settings)
                    await asyncio.sleep(1.0)
                    continue
                msg = consumer.poll(0)
                if msg is None:
                    _report_lag(settings)
                    await asyncio.sleep(0.05)
                    continue
                if msg.error():
                    log.warning("consumer error: %s", msg.error())
                    continue
                event = json.loads(msg.value().decode("utf-8"))
                log.info("notification sent for payment %s", event.get("payment_id"))
            except Exception as exc:  # pragma: no cover - env dependent
                log.error("consumer loop error: %s", exc)
                await asyncio.sleep(1.0)

    asyncio.run(_run())


def create_app() -> FastAPI:
    settings = Settings()
    app = create_service_app(SERVICE, "Notifications Service")
    telemetry.init_telemetry(SERVICE, settings.otel_endpoint)
    meter = telemetry.get_meter(SERVICE)
    meter.create_gauge("kafka.consumer.lag", unit="messages")
    threading.Thread(target=_consume_loop, args=(settings,), daemon=True).start()
    return app


def main() -> None:
    import uvicorn

    port = int(os.getenv("SIM_SERVICE_PORT", str(DEFAULT_PORTS[SERVICE])))
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
