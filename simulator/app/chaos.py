from __future__ import annotations

import os

import redis

from app.config import Settings

_PREFIX = "sim:chaos"


def get_client(settings: Settings | None = None) -> redis.Redis:
    settings = settings or Settings()
    return redis.Redis.from_url(
        settings.redis_url, decode_responses=True, socket_timeout=1.0
    )


def _key(service: str, flag: str) -> str:
    return f"{_PREFIX}:{service}:{flag}"


def get_flag(service: str, flag: str, default: float = 0.0) -> float:
    try:
        client = get_client()
        raw = client.get(_key(service, flag))
    except Exception:
        return default
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def set_flag(service: str, flag: str, value: float) -> None:
    client = get_client()
    client.set(_key(service, flag), str(value))


def clear_all(settings: Settings | None = None) -> None:
    client = get_client(settings)
    for key in client.scan_iter(match=f"{_PREFIX}:*"):
        client.delete(key)


def consumer_stopped(service: str) -> bool:
    return get_flag(service, "consumer_stopped", 0.0) > 0.5
