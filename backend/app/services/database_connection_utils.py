from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import create_engine, text


DEFAULT_PORTS = {
    "postgresql": 5432,
    "postgres": 5432,
    "mysql": 3306,
    "mariadb": 3306,
    "sqlite": 0,
    "clickhouse": 9000,
}


@dataclass(frozen=True)
class DatabaseConnectionPayload:
    dialect: str
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None


def normalize_dialect(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value in {"postgres", "postgresql"}:
        return "postgresql"
    return value


def build_connection_url(connection: DatabaseConnectionPayload) -> str:
    dialect = normalize_dialect(connection.dialect)
    if dialect == "sqlite":
        return f"sqlite:///{connection.database or ':memory:'}"

    driver_prefix = {
        "postgresql": "postgresql+psycopg2",
        "mysql": "mysql+pymysql",
        "mariadb": "mysql+pymysql",
        "clickhouse": "clickhouse+native",
    }.get(dialect, dialect)

    user = connection.username or ""
    password = f":{connection.password}" if connection.password else ""
    credentials = f"{user}{password}@" if user or password else ""
    host = connection.host or "localhost"
    port = connection.port or DEFAULT_PORTS.get(dialect)
    port_segment = f":{port}" if port else ""
    database = f"/{connection.database}" if connection.database else ""
    return f"{driver_prefix}://{credentials}{host}{port_segment}{database}"


def create_connection_engine(connection: DatabaseConnectionPayload):
    url = build_connection_url(connection)
    return create_engine(url, pool_pre_ping=True)


def ping_engine(engine) -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

