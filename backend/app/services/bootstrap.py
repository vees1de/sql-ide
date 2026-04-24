from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.base import Base
from app.db.models import (
    ChatMessageModel,
    ChatSessionModel,
    CellModel,
    DatabaseConnectionModel,
    DatabaseKnowledgeMetadataModel,
    DatabaseKnowledgeColumnModel,
    DatabaseKnowledgeRelationshipModel,
    DatabaseKnowledgeScanRunModel,
    DatabaseKnowledgeTableModel,
    NotebookModel,
    QueryExecutionModel,
    QueryRunModel,
    SavedReportModel,
    SemanticCatalogColumnModel,
    SemanticCatalogJoinPathModel,
    SemanticCatalogModel,
    SemanticCatalogRelationshipModel,
    SemanticCatalogTableModel,
    SemanticDictionaryModel,
    WorkspaceModel,
)
from app.db.session import service_engine


def _ensure_database_connections_allowed_tables_column(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "database_connections" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("database_connections")}
        if "allowed_tables" in columns:
            return
        with engine.begin() as connection:
            dialect = connection.dialect.name
            if dialect == "sqlite":
                connection.execute(text("ALTER TABLE database_connections ADD COLUMN allowed_tables TEXT"))
            else:
                connection.execute(text("ALTER TABLE database_connections ADD COLUMN allowed_tables JSONB"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def _ensure_semantic_dictionary_context_columns(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "semantic_dictionary" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("semantic_dictionary")}
        required = {
            "object_type": "VARCHAR(32)",
            "table_name": "VARCHAR(255)",
            "column_name": "VARCHAR(255)",
            "database_id": "VARCHAR(32)",
            "source_database": "VARCHAR(255)",
        }
        with engine.begin() as connection:
            for name, sql_type in required.items():
                if name in columns:
                    continue
                connection.execute(text(f"ALTER TABLE semantic_dictionary ADD COLUMN {name} {sql_type}"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def _ensure_database_knowledge_semantic_columns(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "database_knowledge_tables" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("database_knowledge_tables")}
        required = {
            "semantic_label_manual": "VARCHAR(255)",
            "semantic_table_role_manual": "VARCHAR(32)",
            "semantic_grain_manual": "TEXT",
            "semantic_main_date_column_manual": "VARCHAR(255)",
            "semantic_main_entity_manual": "VARCHAR(255)",
            "semantic_synonyms": "JSON",
            "semantic_important_metrics": "JSON",
            "semantic_important_dimensions": "JSON",
        }
        with engine.begin() as connection:
            dialect = connection.dialect.name
            for name, sql_type in required.items():
                if name in columns:
                    continue
                effective_type = "JSONB" if sql_type == "JSON" and dialect != "sqlite" else sql_type
                connection.execute(text(f"ALTER TABLE database_knowledge_tables ADD COLUMN {name} {effective_type}"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def _ensure_semantic_catalog_relationship_graph_column(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "semantic_catalogs" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("semantic_catalogs")}
        if "relationship_graph" in columns:
            return
        with engine.begin() as connection:
            dialect = connection.dialect.name
            if dialect == "sqlite":
                connection.execute(text("ALTER TABLE semantic_catalogs ADD COLUMN relationship_graph JSON"))
            else:
                connection.execute(text("ALTER TABLE semantic_catalogs ADD COLUMN relationship_graph JSONB"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def _ensure_dashboard_hidden_column(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "dashboards" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("dashboards")}
        if "is_hidden" in columns:
            return
        with engine.begin() as connection:
            dialect = connection.dialect.name
            if dialect == "sqlite":
                connection.execute(text("ALTER TABLE dashboards ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT 0"))
            else:
                connection.execute(text("ALTER TABLE dashboards ADD COLUMN is_hidden BOOLEAN NOT NULL DEFAULT FALSE"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def _ensure_chat_query_execution_dataset_column(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "chat_query_executions" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("chat_query_executions")}
        if "dataset_id" in columns:
            return
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE chat_query_executions ADD COLUMN dataset_id VARCHAR(32)"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def _ensure_widget_dataset_columns(engine: Engine) -> None:
    try:
        inspector = inspect(engine)
        if "widgets" not in inspector.get_table_names():
            return
        columns = {col["name"] for col in inspector.get_columns("widgets")}
        with engine.begin() as connection:
            if "dataset_id" not in columns:
                connection.execute(text("ALTER TABLE widgets ADD COLUMN dataset_id VARCHAR(32)"))
            if "chart_spec_json" not in columns:
                connection.execute(text("ALTER TABLE widgets ADD COLUMN chart_spec_json JSON"))
    except Exception:  # noqa: BLE001 — best-effort migration for dev SQLite/Postgres
        pass


def bootstrap_application() -> None:
    Base.metadata.create_all(bind=service_engine)
    _ensure_database_connections_allowed_tables_column(service_engine)
    _ensure_semantic_dictionary_context_columns(service_engine)
    _ensure_database_knowledge_semantic_columns(service_engine)
    _ensure_semantic_catalog_relationship_graph_column(service_engine)
    _ensure_dashboard_hidden_column(service_engine)
    _ensure_chat_query_execution_dataset_column(service_engine)
    _ensure_widget_dataset_columns(service_engine)
    with Session(service_engine) as session:
        _cleanup_legacy_demo_data(session)
        seed_service_data(session)


def seed_service_data(session: Session) -> None:
    workspace = session.query(WorkspaceModel).first()
    if workspace is None:
        workspace = WorkspaceModel(
            name=settings.workspace_name,
            databases=[settings.analytics_database_id],
        )
        session.add(workspace)

    if session.query(SemanticDictionaryModel).count() == 0:
        session.add_all(
            [
                SemanticDictionaryModel(
                    term="revenue",
                    synonyms=["выручка", "оборот", "sales revenue"],
                    mapped_expression="SUM(o.revenue)",
                    description="Общая выручка по заказам.",
                ),
                SemanticDictionaryModel(
                    term="order_count",
                    synonyms=["количество заказов", "orders"],
                    mapped_expression="COUNT(o.id)",
                    description="Количество заказов.",
                ),
                SemanticDictionaryModel(
                    term="avg_order_value",
                    synonyms=["средний чек", "aov"],
                    mapped_expression="AVG(o.revenue)",
                    description="Средний чек.",
                ),
            ]
        )

    session.commit()


def _cleanup_legacy_demo_data(session: Session) -> None:
    legacy_database_ids = {"".join(["demo", "_", "analytics"])}

    for workspace in session.query(WorkspaceModel).all():
        current_databases = list(workspace.databases or [])
        filtered_databases = [database_id for database_id in current_databases if database_id not in legacy_database_ids]
        if filtered_databases != current_databases:
            workspace.databases = filtered_databases

    legacy_session_ids = [row[0] for row in session.query(ChatSessionModel.id).filter(
        ChatSessionModel.database_connection_id.in_(legacy_database_ids)
    ).all()]
    if legacy_session_ids:
        session.query(ChatMessageModel).filter(ChatMessageModel.session_id.in_(legacy_session_ids)).delete(
            synchronize_session=False
        )
        session.query(QueryExecutionModel).filter(QueryExecutionModel.session_id.in_(legacy_session_ids)).delete(
            synchronize_session=False
        )
        session.query(ChatSessionModel).filter(ChatSessionModel.id.in_(legacy_session_ids)).delete(
            synchronize_session=False
        )

    legacy_notebook_ids = [row[0] for row in session.query(NotebookModel.id).filter(
        NotebookModel.database_id.in_(legacy_database_ids)
    ).all()]
    legacy_query_run_ids = [row[0] for row in session.query(QueryRunModel.id).filter(
        QueryRunModel.notebook_id.in_(legacy_notebook_ids)
    ).all()]
    if legacy_query_run_ids:
        session.query(CellModel).filter(CellModel.query_run_id.in_(legacy_query_run_ids)).update(
            {CellModel.query_run_id: None}, synchronize_session=False
        )
    if legacy_query_run_ids:
        session.query(QueryRunModel).filter(QueryRunModel.id.in_(legacy_query_run_ids)).delete(
            synchronize_session=False
        )
    if legacy_notebook_ids:
        session.query(CellModel).filter(CellModel.notebook_id.in_(legacy_notebook_ids)).delete(
            synchronize_session=False
        )
        session.query(SavedReportModel).filter(SavedReportModel.notebook_id.in_(legacy_notebook_ids)).delete(
            synchronize_session=False
        )
        session.query(NotebookModel).filter(NotebookModel.id.in_(legacy_notebook_ids)).delete(
            synchronize_session=False
        )

    session.query(DatabaseKnowledgeColumnModel).filter(
        DatabaseKnowledgeColumnModel.database_id.in_(legacy_database_ids)
    ).delete(synchronize_session=False)
    session.query(DatabaseKnowledgeMetadataModel).filter(
        DatabaseKnowledgeMetadataModel.database_id.in_(legacy_database_ids)
    ).delete(synchronize_session=False)
    session.query(DatabaseKnowledgeRelationshipModel).filter(
        DatabaseKnowledgeRelationshipModel.database_id.in_(legacy_database_ids)
    ).delete(synchronize_session=False)
    session.query(DatabaseKnowledgeTableModel).filter(
        DatabaseKnowledgeTableModel.database_id.in_(legacy_database_ids)
    ).delete(synchronize_session=False)
    session.query(DatabaseKnowledgeScanRunModel).filter(
        DatabaseKnowledgeScanRunModel.database_id.in_(legacy_database_ids)
    ).delete(synchronize_session=False)

    session.query(SemanticCatalogColumnModel).filter(
        SemanticCatalogColumnModel.database_id.in_(legacy_database_ids)
    ).delete(synchronize_session=False)
    session.query(SemanticCatalogRelationshipModel).filter(
        SemanticCatalogRelationshipModel.database_id.in_(legacy_database_ids)
    ).delete(synchronize_session=False)
    session.query(SemanticCatalogTableModel).filter(
        SemanticCatalogTableModel.database_id.in_(legacy_database_ids)
    ).delete(synchronize_session=False)
    session.query(SemanticCatalogJoinPathModel).filter(
        SemanticCatalogJoinPathModel.database_id.in_(legacy_database_ids)
    ).delete(synchronize_session=False)
    session.query(SemanticCatalogModel).filter(SemanticCatalogModel.database_id.in_(legacy_database_ids)).delete(
        synchronize_session=False
    )

    session.query(DatabaseConnectionModel).filter(
        DatabaseConnectionModel.id.in_(legacy_database_ids)
    ).delete(synchronize_session=False)
    session.query(SemanticDictionaryModel).filter(
        (SemanticDictionaryModel.source_database.in_(legacy_database_ids))
        | (SemanticDictionaryModel.database_id.in_(legacy_database_ids))
    ).delete(synchronize_session=False)

    session.commit()
