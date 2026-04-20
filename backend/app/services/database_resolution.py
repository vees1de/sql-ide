from __future__ import annotations

from weakref import WeakValueDictionary
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DatabaseConnectionModel
from app.db.session import analytics_engine
from app.services.database_connection_utils import (
    DatabaseConnectionPayload,
    create_connection_engine,
    normalize_dialect,
)


_ENGINE_CACHE: WeakValueDictionary[str, Any] = WeakValueDictionary()


def resolve_dialect(db: Session, database_connection_id: str) -> str:
    if database_connection_id == settings.demo_database_id:
        return normalize_dialect(analytics_engine.dialect.name)
    connection = _get_connection(db, database_connection_id)
    return normalize_dialect(connection.dialect or analytics_engine.dialect.name)


def resolve_engine(db: Session, database_connection_id: str):
    if database_connection_id == settings.demo_database_id:
        return analytics_engine

    cached = _ENGINE_CACHE.get(database_connection_id)
    if cached is not None:
        return cached

    connection = _get_connection(db, database_connection_id)
    engine = create_connection_engine(
        DatabaseConnectionPayload(
            dialect=connection.dialect,
            host=connection.host,
            port=connection.port,
            database=connection.database,
            username=connection.username,
            password=connection.password,
        )
    )
    _ENGINE_CACHE[database_connection_id] = engine
    return engine


def resolve_allowed_tables(db: Session, database_connection_id: str, engine: Any | None = None) -> list[str]:
    if engine is None:
        engine = resolve_engine(db, database_connection_id)

    discovered_tables = _list_table_names(engine)
    if database_connection_id == settings.demo_database_id:
        configured = [str(table) for table in settings.allowed_tables if str(table)]
        if configured and discovered_tables:
            allowed = [table for table in discovered_tables if table in set(configured)]
            return allowed or configured
        return configured or discovered_tables

    connection = _get_connection(db, database_connection_id)
    allowed_tables = connection.allowed_tables if isinstance(connection.allowed_tables, list) else None
    if allowed_tables is not None:
        configured = [str(table) for table in allowed_tables if str(table)]
        if discovered_tables:
            if not configured:
                return discovered_tables
            allowed = [table for table in discovered_tables if table in set(configured)]
            return allowed or configured
        if configured:
            return configured
        return [str(table) for table in settings.allowed_tables if str(table)]

    if discovered_tables:
        return discovered_tables
    return [str(table) for table in settings.allowed_tables if str(table)]


def _get_connection(db: Session, database_connection_id: str) -> DatabaseConnectionModel:
    connection = (
        db.query(DatabaseConnectionModel)
        .filter(DatabaseConnectionModel.id == database_connection_id)
        .first()
    )
    if connection is None:
        raise ValueError("Database connection not found.")
    return connection


def _list_table_names(engine: Any) -> list[str]:
    inspector = sa_inspect(engine)
    dialect_name = normalize_dialect(getattr(engine.dialect, "name", ""))
    if dialect_name.startswith("postgres"):
        try:
            table_names = inspector.get_table_names(schema="public")
        except Exception:  # noqa: BLE001
            table_names = inspector.get_table_names()
    else:
        table_names = inspector.get_table_names()

    return sorted({str(name) for name in table_names if str(name).strip()})
