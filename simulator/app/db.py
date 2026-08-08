from __future__ import annotations

import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import Settings

log = logging.getLogger(__name__)

_engine = None


class Base(DeclarativeBase):
    pass


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(Settings().database_url, pool_pre_ping=True)
    return _engine


def create_tables() -> None:
    from app import models  # noqa: F401 - register tables

    Base.metadata.create_all(get_engine())


def ensure_demo_schema() -> None:
    """Create the demo schema in the demo database if it does not exist."""
    engine = create_engine(Settings().database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS demo"))
            conn.commit()
    finally:
        engine.dispose()


def new_session() -> Session:
    return Session(get_engine())
