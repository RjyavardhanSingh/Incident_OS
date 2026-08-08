from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

SERVICES = ("gateway", "auth", "orders", "payments", "inventory", "notifications")

DEFAULT_PORTS = {
    "gateway": 8010,
    "auth": 8011,
    "orders": 8012,
    "payments": 8013,
    "inventory": 8014,
    "notifications": 8015,
}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    otel_endpoint: str = field(
        default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:8000/api/v1/otlp")
    )
    otel_protocol: str = field(
        default_factory=lambda: os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    )
    service_name: str = field(
        default_factory=lambda: os.getenv("SIM_SERVICE_NAME", "gateway")
    )
    service_port: int = field(
        default_factory=lambda: _int("SIM_SERVICE_PORT", 8010)
    )
    database_url: str = field(
        default_factory=lambda: os.getenv(
            "SIM_DATABASE_URL",
            "postgresql+psycopg://incident_os:incident_os_dev@localhost:5433/incident_os_dev",
        )
    )
    redis_url: str = field(
        default_factory=lambda: os.getenv("SIM_REDIS_URL", "redis://localhost:6379/0")
    )
    kafka_bootstrap: str = field(
        default_factory=lambda: os.getenv("SIM_KAFKA_BOOTSTRAP", "localhost:9092")
    )
    auth_url: str = field(default_factory=lambda: os.getenv("SIM_AUTH_URL", "http://localhost:8011"))
    orders_url: str = field(default_factory=lambda: os.getenv("SIM_ORDERS_URL", "http://localhost:8012"))
    payments_url: str = field(default_factory=lambda: os.getenv("SIM_PAYMENTS_URL", "http://localhost:8013"))
    inventory_url: str = field(default_factory=lambda: os.getenv("SIM_INVENTORY_URL", "http://localhost:8014"))
    notifications_url: str = field(
        default_factory=lambda: os.getenv("SIM_NOTIFICATIONS_URL", "http://localhost:8015")
    )
    gateway_url: str = field(default_factory=lambda: os.getenv("SIM_GATEWAY_URL", "http://localhost:8010"))


def get_settings() -> Settings:
    return Settings()
