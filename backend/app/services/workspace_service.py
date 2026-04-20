from __future__ import annotations

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DatabaseConnectionModel, DatabaseKnowledgeScanRunModel, WorkspaceModel
from app.db.session import analytics_engine
from app.schemas.workspace import (
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
    DatabaseDescriptor,
    SchemaPreviewResponse,
    SchemaPreviewTable,
    WorkspaceCreate,
)
from app.services.database_connection_utils import (
    DatabaseConnectionPayload,
    create_connection_engine,
    normalize_dialect,
    ping_engine,
)
from app.services.knowledge_service import KnowledgeService


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


class WorkspaceService:
    def __init__(self) -> None:
        self.knowledge_service = KnowledgeService()

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
                knowledge_status=self._knowledge_status(db, settings.demo_database_id),
                last_scan_at=self._last_scan_at(db, settings.demo_database_id),
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
                    knowledge_status=self._knowledge_status(db, connection.id),
                    last_scan_at=self._last_scan_at(db, connection.id),
                )
            )
        return descriptors

    def preview_schema(self, payload: DatabaseConnectionCreate) -> SchemaPreviewResponse:
        engine = create_connection_engine(
            DatabaseConnectionPayload(
                dialect=payload.dialect,
                host=payload.host,
                port=payload.port,
                database=payload.database,
                username=payload.username,
                password=payload.password,
            )
        )
        try:
            ping_engine(engine)
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
        dialect = normalize_dialect(payload.dialect)
        status = "connected"
        table_count = payload.table_count or 0
        allowed_tables_json: list[str] | None = None
        imported_count = 0

        try:
            engine = create_connection_engine(
                DatabaseConnectionPayload(
                    dialect=payload.dialect,
                    host=payload.host,
                    port=payload.port,
                    database=payload.database,
                    username=payload.username,
                    password=payload.password,
                )
            )
            try:
                ping_engine(engine)
                _, discovered_names = _introspect_engine_tables(engine)
                table_count = len(discovered_names)
                chosen = (
                    [name for name in (payload.allowed_tables or []) if name in discovered_names]
                    if payload.allowed_tables is not None
                    else discovered_names
                )
                if not chosen and discovered_names:
                    chosen = discovered_names
                allowed_tables_json = chosen
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

        if payload.import_schema_to_dictionary and connection_model.status == "connected":
            try:
                scan = self.knowledge_service.scan_database(
                    db,
                    connection_model.id,
                    scan_type="full",
                    sync_dictionary=True,
                )
                imported_count = int(scan.summary.get("dictionary_entries_imported", 0) or 0)
            except Exception:  # noqa: BLE001
                imported_count = 0
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

    def _knowledge_status(self, db: Session, database_id: str) -> str:
        latest = (
            db.query(DatabaseKnowledgeScanRunModel)
            .filter(DatabaseKnowledgeScanRunModel.database_id == database_id)
            .order_by(DatabaseKnowledgeScanRunModel.started_at.desc())
            .first()
        )
        return latest.status if latest is not None else "not_scanned"

    def _last_scan_at(self, db: Session, database_id: str) -> str | None:
        latest = (
            db.query(DatabaseKnowledgeScanRunModel)
            .filter(DatabaseKnowledgeScanRunModel.database_id == database_id)
            .order_by(DatabaseKnowledgeScanRunModel.started_at.desc())
            .first()
        )
        if latest is None or latest.finished_at is None:
            return None
        return latest.finished_at.isoformat()
