"""Incident OS simulator CLI.

Commands:
  services         run all six demo services as subprocesses
  load             drive traffic through the gateway
  chaos            set/clear chaos flags in Redis
  deployment       emit a deployment metadata log to Incident OS
  seed-db          create the demo database and tables
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

from app.config import DEFAULT_PORTS, SERVICES, Settings


def _env_for(service: str) -> dict:
    env = os.environ.copy()
    env["SIM_SERVICE_NAME"] = service
    env["SIM_SERVICE_PORT"] = str(DEFAULT_PORTS[service])
    return env


def cmd_services(_args: argparse.Namespace) -> None:
    processes = []
    for service in SERVICES:
        env = _env_for(service)
        proc = subprocess.Popen(
            [sys.executable, "-m", f"app.services.{service}"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        processes.append((service, proc))
        print(f"started {service} (pid {proc.pid}) on {DEFAULT_PORTS[service]}")
        time.sleep(0.8)
    try:
        while all(proc.poll() is None for _, proc in processes):
            time.sleep(1)
        dead = [name for name, proc in processes if proc.poll() is not None]
        print(f"service exited: {dead}", file=sys.stderr)
    finally:
        for _, proc in processes:
            if proc.poll() is None:
                proc.terminate()


def cmd_load(args: argparse.Namespace) -> None:
    import asyncio
    import random

    import httpx

    settings = Settings()
    rate = args.rate
    interval = 1.0 / rate if rate > 0 else 1.0

    async def worker(wid: int) -> None:
        async with httpx.AsyncClient(timeout=15.0) as client:
            while True:
                await client.post(
                    settings.gateway_url.rstrip("/") + "/api/orders/checkout",
                    json={
                        "items": [{"sku": f"sku-{random.randint(1, 50)}", "qty": 1}],
                        "amount": random.randint(50, 500),
                    },
                )
                await asyncio.sleep(interval)

    async def main() -> None:
        tasks = [asyncio.create_task(worker(i)) for i in range(args.workers)]
        await asyncio.gather(*tasks)

    print(f"driving traffic: rate={rate}/s workers={args.workers}")
    asyncio.run(main())


def cmd_chaos(args: argparse.Namespace) -> None:
    from app import chaos

    if args.action == "clear":
        chaos.clear_all()
        print("cleared all chaos flags")
        return
    service, flag, value = args.service, args.flag, float(args.value)
    chaos.set_flag(service, flag, value)
    print(f"set sim:chaos:{service}:{flag} = {value}")


def cmd_deployment(args: argparse.Namespace) -> None:
    from opentelemetry._logs import LogRecord
    from opentelemetry._logs import get_logger, set_logger_provider
    from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    from app.config import Settings as _Settings

    settings = _Settings()
    provider = LoggerProvider(
        resource=Resource.create({SERVICE_NAME: args.service})
    )
    provider.add_log_record_processor(
        BatchLogRecordProcessor(
            OTLPLogExporter(endpoint=f"{settings.otel_endpoint}/v1/logs")
        )
    )
    set_logger_provider(provider)
    logger = get_logger("simulator.deployment")
    logger.emit(
        LogRecord(
            body=f"deploy {args.version}",
            severity_text="INFO",
            severity_number=9,
            attributes={
                "source_type": "deployment",
                "service": args.service,
                "version": args.version,
                "config": args.config or "",
            },
        )
    )
    provider.force_flush()
    time.sleep(1)
    print(f"emitted deployment log for {args.service} v{args.version}")


def cmd_seed_db(_args: argparse.Namespace) -> None:
    from app import db

    db.ensure_demo_schema()
    db.create_tables()
    print("demo database ready")


def main() -> None:
    parser = argparse.ArgumentParser(prog="simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("services")
    p.set_defaults(func=cmd_services)

    p = sub.add_parser("load")
    p.add_argument("--rate", type=float, default=20.0)
    p.add_argument("--workers", type=int, default=1)
    p.set_defaults(func=cmd_load)

    p = sub.add_parser("chaos")
    p.add_argument("action", choices=["set", "clear"])
    p.add_argument("service", nargs="?")
    p.add_argument("flag", nargs="?")
    p.add_argument("value", nargs="?", default="0")
    p.set_defaults(func=cmd_chaos)

    p = sub.add_parser("deployment")
    p.add_argument("service")
    p.add_argument("version")
    p.add_argument("--config", default="")
    p.set_defaults(func=cmd_deployment)

    p = sub.add_parser("seed-db")
    p.set_defaults(func=cmd_seed_db)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
