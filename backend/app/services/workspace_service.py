from __future__ import annotations

from sqlalchemy import create_engine, inspect as sa_inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DatabaseConnectionModel, WorkspaceModel
from app.db.session import analytics_engine
from app.schemas.workspace import (
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
    DatabaseDescriptor,
    SchemaPreviewResponse,
    SchemaPreviewTable,
    WorkspaceCreate,
)
from app.services.dictionary_service import DictionaryService


DEFAULT_PORTS = {
    "postgresql": 5432,
    "postgres": 5432,
    "mysql": 3306,
    "mariadb": 3306,
    "sqlite": 0,
    "clickhouse": 9000,
}


def _normalize_dialect(raw: str) -> str:
    value = (raw or "").strip().lower()
    if value in {"postgres", "postgresql"}:
        return "postgresql"
    return value


dictionary_service = DictionaryService()


def _introspect_engine_tables(engine) -> tuple[list[dict[str, object]], list[str]]:
    inspector = sa_inspect(engine)
    dialect_name = (engine.dialect.name or "").lower()
    if dialect_name in ("postgresql", "postgres"):
        table_names = inspector.get_table_names(schema="public")
    else:
        table_names = inspector.get_table_names()
    tables: list[dict[str, object]] = []
    for table_name in table_names:
        columns = inspector.get_columns(table_name)
        tables.append(
            {
                "name": table_name,
                "columns": [{"name": c["name"], "type": str(c["type"])} for c in columns],
            }
        )
    return tables, table_names


def _build_url(connection: DatabaseConnectionCreate) -> str:
    dialect = _normalize_dialect(connection.dialect)
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


class WorkspaceService:
    def list_workspaces(self, db: Session) -> list[WorkspaceModel]:
        return db.query(WorkspaceModel).order_by(WorkspaceModel.created_at.asc()).all()

    def create_workspace(self, db: Session, payload: WorkspaceCreate) -> WorkspaceModel:
        workspace = WorkspaceModel(name=payload.name, databases=payload.databases)
        db.add(workspace)
        db.commit()
        db.refresh(workspace)
        return workspace

    def list_databases(self, db: Session) -> list[DatabaseDescriptor]:
        descriptors: list[DatabaseDescriptor] = [
            DatabaseDescriptor(
                id=settings.demo_database_id,
                name=settings.demo_database_name,
                dialect=analytics_engine.dialect.name,
                description=(
                    "Built-in demo analytics database."
                    if settings.analytics_uses_demo_data
                    else "Configured analytical database."
                ),
                read_only=True,
                is_demo=settings.analytics_uses_demo_data,
                status="connected",
            )
        ]

        connections = (
            db.query(DatabaseConnectionModel)
            .order_by(DatabaseConnectionModel.created_at.asc())
            .all()
        )
        for connection in connections:
            allowed = connection.allowed_tables
            allowed_list = allowed if isinstance(allowed, list) else None
            descriptors.append(
                DatabaseDescriptor(
                    id=connection.id,
                    name=connection.name,
                    dialect=connection.dialect,
                    description=connection.description or "",
                    read_only=(connection.read_only or "true").lower() == "true",
                    is_demo=False,
                    host=connection.host,
                    port=connection.port,
                    database=connection.database,
                    username=connection.username,
                    table_count=connection.table_count or 0,
                    status=connection.status or "connected",
                    allowed_tables=allowed_list,
                )
            )
        return descriptors

    def preview_schema(self, payload: DatabaseConnectionCreate) -> SchemaPreviewResponse:
        url = _build_url(payload)
        engine = create_engine(url, pool_pre_ping=True)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            tables, names = _introspect_engine_tables(engine)
        finally:
            engine.dispose()
        preview_tables = [
            SchemaPreviewTable(name=str(t["name"]), columns=[str(c["name"]) for c in t["columns"]]) for t in tables
        ]
        return SchemaPreviewResponse(tables=preview_tables, table_names=names)

    def create_database(
        self, db: Session, payload: DatabaseConnectionCreate
    ) -> tuple[DatabaseConnectionModel, int]:
        dialect = _normalize_dialect(payload.dialect)
        status = "connected"
        table_count = payload.table_count or 0
        allowed_tables_json: list[str] | None = None
        imported_count = 0

        try:
            url = _build_url(payload)
            engine = create_engine(url, pool_pre_ping=True)
            try:
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))
                introspected, discovered_names = _introspect_engine_tables(engine)
                table_count = len(discovered_names)
                chosen = (
                    [name for name in (payload.allowed_tables or []) if name in discovered_names]
                    if payload.allowed_tables is not None
                    else discovered_names
                )
                if not chosen and discovered_names:
                    chosen = discovered_names
                allowed_tables_json = chosen

                if payload.import_schema_to_dictionary and chosen:
                    table_subset = [t for t in introspected if str(t.get("name")) in set(chosen)]
                    imported_count = dictionary_service.import_schema_tables(
                        db,
                        table_subset,
                        database_label=payload.name,
                    )
            finally:
                engine.dispose()
        except Exception:  # noqa: BLE001 — we want to surface failures as "syncing"
            status = "syncing"

        connection_model = DatabaseConnectionModel(
            name=payload.name,
            dialect=dialect,
            host=payload.host,
            port=payload.port,
            database=payload.database,
            username=payload.username,
            password=payload.password,
            description=payload.description or "",
            read_only="true" if payload.read_only else "false",
            table_count=table_count,
            allowed_tables=allowed_tables_json,
            status=status,
        )
        db.add(connection_model)
        db.commit()
        db.refresh(connection_model)
        return connection_model, imported_count

    def update_database(
        self, db: Session, database_id: str, payload: DatabaseConnectionUpdate
    ) -> DatabaseConnectionModel | None:
        if database_id == settings.demo_database_id:
            return None
        connection = (
            db.query(DatabaseConnectionModel).filter(DatabaseConnectionModel.id == database_id).first()
        )
        if connection is None:
            return None
        if payload.allowed_tables is not None:
            connection.allowed_tables = payload.allowed_tables
        db.commit()
        db.refresh(connection)
        return connection

    def delete_database(self, db: Session, database_id: str) -> bool:
        if database_id == settings.demo_database_id:
            return False
        connection = (
            db.query(DatabaseConnectionModel)
            .filter(DatabaseConnectionModel.id == database_id)
            .first()
        )
        if connection is None:
            return False
        db.delete(connection)
        db.commit()
        return True
