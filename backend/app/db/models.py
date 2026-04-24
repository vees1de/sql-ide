from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.utcnow()


class WorkspaceModel(Base):
    __tablename__ = "workspaces"

    id = Column(String(32), primary_key=True, default=generate_id)
    name = Column(String(255), nullable=False)
    databases = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    notebooks = relationship("NotebookModel", back_populates="workspace", cascade="all, delete-orphan")


class NotebookModel(Base):
    __tablename__ = "notebooks"

    id = Column(String(32), primary_key=True, default=generate_id)
    workspace_id = Column(String(32), ForeignKey("workspaces.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    database_id = Column(String(255), nullable=False)
    status = Column(String(32), nullable=False, default="draft")
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    workspace = relationship("WorkspaceModel", back_populates="notebooks")
    cells = relationship("CellModel", back_populates="notebook", cascade="all, delete-orphan")
    query_runs = relationship("QueryRunModel", back_populates="notebook", cascade="all, delete-orphan")
    reports = relationship("SavedReportModel", back_populates="notebook", cascade="all, delete-orphan")


class CellModel(Base):
    __tablename__ = "cells"

    id = Column(String(32), primary_key=True, default=generate_id)
    notebook_id = Column(String(32), ForeignKey("notebooks.id"), nullable=False, index=True)
    query_run_id = Column(String(32), ForeignKey("query_runs.id"), nullable=True, index=True)
    type = Column(String(32), nullable=False)
    position = Column(Integer, nullable=False, index=True)
    content = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    notebook = relationship("NotebookModel", back_populates="cells")
    query_run = relationship("QueryRunModel", back_populates="cells", foreign_keys="CellModel.query_run_id")


class QueryRunModel(Base):
    __tablename__ = "query_runs"

    id = Column(String(32), primary_key=True, default=generate_id)
    notebook_id = Column(String(32), ForeignKey("notebooks.id"), nullable=False, index=True)
    prompt_cell_id = Column(String(32), ForeignKey("cells.id"), nullable=False, index=True)
    prompt_text = Column(Text, nullable=False)
    sql = Column(Text, nullable=False, default="")
    explanation = Column(JSON, nullable=False, default=dict)
    agent_trace = Column(JSON, nullable=False, default=dict)
    confidence = Column(Float, nullable=False, default=0.0)
    execution_time_ms = Column(Integer, nullable=False, default=0)
    row_count = Column(Integer, nullable=False, default=0)
    status = Column(String(32), nullable=False, default="success", index=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    notebook = relationship("NotebookModel", back_populates="query_runs")
    cells = relationship("CellModel", back_populates="query_run", foreign_keys="CellModel.query_run_id")
    prompt_cell = relationship("CellModel", foreign_keys="QueryRunModel.prompt_cell_id")


class SavedReportModel(Base):
    __tablename__ = "saved_reports"

    id = Column(String(32), primary_key=True, default=generate_id)
    notebook_id = Column(String(32), ForeignKey("notebooks.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    schedule = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    notebook = relationship("NotebookModel", back_populates="reports")


class DatabaseConnectionModel(Base):
    __tablename__ = "database_connections"

    id = Column(String(32), primary_key=True, default=generate_id)
    name = Column(String(255), nullable=False)
    dialect = Column(String(64), nullable=False, default="postgresql")
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    database = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)
    description = Column(Text, nullable=False, default="")
    read_only = Column(String(8), nullable=False, default="true")
    table_count = Column(Integer, nullable=False, default=0)
    allowed_tables = Column(JSON, nullable=True)
    status = Column(String(32), nullable=False, default="connected")
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)


class SemanticDictionaryModel(Base):
    __tablename__ = "semantic_dictionary"

    id = Column(String(32), primary_key=True, default=generate_id)
    term = Column(String(255), nullable=False, unique=True)
    synonyms = Column(JSON, nullable=False, default=list)
    mapped_expression = Column(String(255), nullable=False)
    description = Column(Text, nullable=False, default="")
    object_type = Column(String(32), nullable=True)
    table_name = Column(String(255), nullable=True)
    column_name = Column(String(255), nullable=True)
    database_id = Column(String(32), nullable=True, index=True)
    source_database = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)


class DatabaseKnowledgeScanRunModel(Base):
    __tablename__ = "database_knowledge_scan_runs"

    id = Column(String(32), primary_key=True, default=generate_id)
    database_id = Column(String(32), nullable=False, index=True)
    database_label = Column(String(255), nullable=False)
    dialect = Column(String(64), nullable=False, default="postgresql")
    scan_type = Column(String(32), nullable=False, default="full")
    status = Column(String(32), nullable=False, default="queued", index=True)
    stage = Column(String(64), nullable=False, default="queued")
    summary = Column(JSON, nullable=False, default=dict)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    finished_at = Column(DateTime, nullable=True, index=True)


class DatabaseKnowledgeMetadataModel(Base):
    __tablename__ = "database_knowledge_metadata"

    database_id = Column(String(32), primary_key=True)
    database_label = Column(String(255), nullable=False)
    dialect = Column(String(64), nullable=False, default="postgresql")
    description_manual = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)


class DatabaseKnowledgeTableModel(Base):
    __tablename__ = "database_knowledge_tables"
    __table_args__ = (
        UniqueConstraint("database_id", "schema_name", "table_name", name="uq_knowledge_table"),
    )

    id = Column(String(32), primary_key=True, default=generate_id)
    database_id = Column(String(32), nullable=False, index=True)
    schema_name = Column(String(255), nullable=False, default="public")
    table_name = Column(String(255), nullable=False)
    object_type = Column(String(32), nullable=False, default="table")
    status = Column(String(32), nullable=False, default="active", index=True)
    column_count = Column(Integer, nullable=False, default=0)
    row_count = Column(Integer, nullable=True)
    primary_key = Column(JSON, nullable=False, default=list)
    description_auto = Column(Text, nullable=True)
    description_manual = Column(Text, nullable=True)
    business_meaning_auto = Column(Text, nullable=True)
    business_meaning_manual = Column(Text, nullable=True)
    domain_auto = Column(String(255), nullable=True)
    domain_manual = Column(String(255), nullable=True)
    semantic_label_manual = Column(String(255), nullable=True)
    semantic_table_role_manual = Column(String(32), nullable=True)
    semantic_grain_manual = Column(Text, nullable=True)
    semantic_main_date_column_manual = Column(String(255), nullable=True)
    semantic_main_entity_manual = Column(String(255), nullable=True)
    semantic_synonyms = Column(JSON, nullable=False, default=list)
    semantic_important_metrics = Column(JSON, nullable=False, default=list)
    semantic_important_dimensions = Column(JSON, nullable=False, default=list)
    tags = Column(JSON, nullable=False, default=list)
    sensitivity = Column(String(64), nullable=True)
    usage_score = Column(Float, nullable=True)
    last_seen_scan_run_id = Column(String(32), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    columns = relationship(
        "DatabaseKnowledgeColumnModel",
        back_populates="table",
        cascade="all, delete-orphan",
    )


class DatabaseKnowledgeColumnModel(Base):
    __tablename__ = "database_knowledge_columns"
    __table_args__ = (
        UniqueConstraint(
            "database_id",
            "schema_name",
            "table_name",
            "column_name",
            name="uq_knowledge_column",
        ),
    )

    id = Column(String(32), primary_key=True, default=generate_id)
    database_id = Column(String(32), nullable=False, index=True)
    table_id = Column(String(32), ForeignKey("database_knowledge_tables.id"), nullable=False, index=True)
    schema_name = Column(String(255), nullable=False, default="public")
    table_name = Column(String(255), nullable=False)
    column_name = Column(String(255), nullable=False)
    data_type = Column(String(255), nullable=False)
    ordinal_position = Column(Integer, nullable=False, default=0)
    is_nullable = Column(Boolean, nullable=False, default=True)
    default_value = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="active", index=True)
    distinct_count = Column(Integer, nullable=True)
    null_ratio = Column(Float, nullable=True)
    min_value = Column(String(255), nullable=True)
    max_value = Column(String(255), nullable=True)
    sample_values = Column(JSON, nullable=False, default=list)
    semantic_label_auto = Column(String(255), nullable=True)
    semantic_label_manual = Column(String(255), nullable=True)
    description_auto = Column(Text, nullable=True)
    description_manual = Column(Text, nullable=True)
    synonyms = Column(JSON, nullable=False, default=list)
    sensitivity = Column(String(64), nullable=True)
    hidden_for_llm = Column(Boolean, nullable=False, default=False)
    last_seen_scan_run_id = Column(String(32), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    table = relationship("DatabaseKnowledgeTableModel", back_populates="columns")


class DatabaseKnowledgeRelationshipModel(Base):
    __tablename__ = "database_knowledge_relationships"
    __table_args__ = (
        UniqueConstraint(
            "database_id",
            "from_schema_name",
            "from_table_name",
            "from_column_name",
            "to_schema_name",
            "to_table_name",
            "to_column_name",
            "relation_type",
            name="uq_knowledge_relationship",
        ),
    )

    id = Column(String(32), primary_key=True, default=generate_id)
    database_id = Column(String(32), nullable=False, index=True)
    from_schema_name = Column(String(255), nullable=False, default="public")
    from_table_name = Column(String(255), nullable=False)
    from_column_name = Column(String(255), nullable=False)
    to_schema_name = Column(String(255), nullable=False, default="public")
    to_table_name = Column(String(255), nullable=False)
    to_column_name = Column(String(255), nullable=False)
    relation_type = Column(String(32), nullable=False, default="physical_fk")
    cardinality = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=False, default=1.0)
    approved = Column(Boolean, nullable=False, default=False)
    is_disabled = Column(Boolean, nullable=False, default=False)
    description_manual = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="active", index=True)
    last_seen_scan_run_id = Column(String(32), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)


class SemanticCatalogModel(Base):
    __tablename__ = "semantic_catalogs"

    id = Column(String(32), primary_key=True, default=generate_id)
    database_id = Column(String(32), nullable=False, index=True)
    dialect = Column(String(64), nullable=False, default="postgresql")
    source_scan_run_id = Column(String(32), nullable=True, index=True)
    active = Column(Boolean, nullable=False, default=True, index=True)
    build_mode = Column(String(64), nullable=False, default="rule_based")
    llm_model = Column(String(255), nullable=True)
    summary = Column(JSON, nullable=False, default=dict)
    notes = Column(JSON, nullable=False, default=list)
    relationship_graph = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    tables = relationship(
        "SemanticCatalogTableModel",
        back_populates="catalog",
        cascade="all, delete-orphan",
        order_by="SemanticCatalogTableModel.schema_name, SemanticCatalogTableModel.table_name",
    )
    columns = relationship(
        "SemanticCatalogColumnModel",
        back_populates="catalog",
        cascade="all, delete-orphan",
    )
    relationships = relationship(
        "SemanticCatalogRelationshipModel",
        back_populates="catalog",
        cascade="all, delete-orphan",
    )
    join_paths = relationship(
        "SemanticCatalogJoinPathModel",
        back_populates="catalog",
        cascade="all, delete-orphan",
    )


class SemanticCatalogTableModel(Base):
    __tablename__ = "semantic_catalog_tables"
    __table_args__ = (
        UniqueConstraint("catalog_id", "schema_name", "table_name", name="uq_semantic_catalog_table"),
    )

    id = Column(String(32), primary_key=True, default=generate_id)
    catalog_id = Column(String(32), ForeignKey("semantic_catalogs.id", ondelete="CASCADE"), nullable=False, index=True)
    database_id = Column(String(32), nullable=False, index=True)
    schema_name = Column(String(255), nullable=False, default="public")
    table_name = Column(String(255), nullable=False)
    label = Column(String(255), nullable=False)
    business_description = Column(Text, nullable=False, default="")
    table_role = Column(String(32), nullable=False, default="dimension")
    grain = Column(Text, nullable=True)
    main_date_column = Column(String(255), nullable=True)
    main_entity = Column(String(255), nullable=True)
    synonyms = Column(JSON, nullable=False, default=list)
    important_metrics = Column(JSON, nullable=False, default=list)
    important_dimensions = Column(JSON, nullable=False, default=list)
    row_count_estimate = Column(Integer, nullable=True)
    primary_key = Column(JSON, nullable=False, default=list)
    indexes = Column(JSON, nullable=False, default=list)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    catalog = relationship("SemanticCatalogModel", back_populates="tables")
    columns = relationship(
        "SemanticCatalogColumnModel",
        back_populates="table",
        cascade="all, delete-orphan",
    )


class SemanticCatalogColumnModel(Base):
    __tablename__ = "semantic_catalog_columns"
    __table_args__ = (
        UniqueConstraint(
            "catalog_id",
            "schema_name",
            "table_name",
            "column_name",
            name="uq_semantic_catalog_column",
        ),
    )

    id = Column(String(32), primary_key=True, default=generate_id)
    catalog_id = Column(String(32), ForeignKey("semantic_catalogs.id", ondelete="CASCADE"), nullable=False, index=True)
    table_id = Column(String(32), ForeignKey("semantic_catalog_tables.id", ondelete="CASCADE"), nullable=False, index=True)
    database_id = Column(String(32), nullable=False, index=True)
    schema_name = Column(String(255), nullable=False, default="public")
    table_name = Column(String(255), nullable=False)
    column_name = Column(String(255), nullable=False)
    label = Column(String(255), nullable=False)
    business_description = Column(Text, nullable=False, default="")
    semantic_types = Column(JSON, nullable=False, default=list)
    analytics_roles = Column(JSON, nullable=False, default=list)
    value_type = Column(String(64), nullable=True)
    aggregation = Column(JSON, nullable=False, default=list)
    filterable = Column(Boolean, nullable=False, default=True)
    groupable = Column(Boolean, nullable=False, default=False)
    sortable = Column(Boolean, nullable=False, default=True)
    synonyms = Column(JSON, nullable=False, default=list)
    example_values = Column(JSON, nullable=False, default=list)
    data_type = Column(String(255), nullable=False)
    nullable = Column(Boolean, nullable=False, default=True)
    default_value = Column(Text, nullable=True)
    max_length = Column(Integer, nullable=True)
    ordinal_position = Column(Integer, nullable=False, default=0)
    is_pk = Column(Boolean, nullable=False, default=False)
    is_fk = Column(Boolean, nullable=False, default=False)
    referenced_table = Column(String(255), nullable=True)
    referenced_column = Column(String(255), nullable=True)
    comment = Column(Text, nullable=True)
    profile = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    catalog = relationship("SemanticCatalogModel", back_populates="columns")
    table = relationship("SemanticCatalogTableModel", back_populates="columns")


class SemanticCatalogRelationshipModel(Base):
    __tablename__ = "semantic_catalog_relationships"
    __table_args__ = (
        UniqueConstraint(
            "catalog_id",
            "from_schema_name",
            "from_table_name",
            "from_column_name",
            "to_schema_name",
            "to_table_name",
            "to_column_name",
            "relationship_type",
            name="uq_semantic_catalog_relationship",
        ),
    )

    id = Column(String(32), primary_key=True, default=generate_id)
    catalog_id = Column(String(32), ForeignKey("semantic_catalogs.id", ondelete="CASCADE"), nullable=False, index=True)
    database_id = Column(String(32), nullable=False, index=True)
    from_schema_name = Column(String(255), nullable=False, default="public")
    from_table_name = Column(String(255), nullable=False)
    from_column_name = Column(String(255), nullable=False)
    to_schema_name = Column(String(255), nullable=False, default="public")
    to_table_name = Column(String(255), nullable=False)
    to_column_name = Column(String(255), nullable=False)
    relationship_type = Column(String(32), nullable=False, default="many-to-one")
    join_type = Column(String(16), nullable=False, default="inner")
    business_meaning = Column(Text, nullable=False, default="")
    join_priority = Column(String(16), nullable=False, default="medium")
    confidence = Column(Float, nullable=False, default=1.0)
    path_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    catalog = relationship("SemanticCatalogModel", back_populates="relationships")


class SemanticCatalogJoinPathModel(Base):
    __tablename__ = "semantic_catalog_join_paths"
    __table_args__ = (
        UniqueConstraint("catalog_id", "path_id", name="uq_semantic_catalog_join_path"),
    )

    id = Column(String(32), primary_key=True, default=generate_id)
    catalog_id = Column(String(32), ForeignKey("semantic_catalogs.id", ondelete="CASCADE"), nullable=False, index=True)
    database_id = Column(String(32), nullable=False, index=True)
    path_id = Column(String(255), nullable=False)
    from_table = Column(String(255), nullable=False)
    to_table = Column(String(255), nullable=False)
    joins = Column(JSON, nullable=False, default=list)
    business_use_case = Column(Text, nullable=False, default="")
    tables = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    catalog = relationship("SemanticCatalogModel", back_populates="join_paths")


# TODO(alembic): the three models below (chat_sessions, chat_messages, chat_query_executions)
# should be included in the first Alembic revision when the knowledge/metadata agent
# introduces proper migrations. For now they are picked up via bootstrap_application()'s
# Base.metadata.create_all.


class ChatSessionModel(Base):
    __tablename__ = "chat_sessions"

    id = Column(String(32), primary_key=True, default=generate_id)
    database_connection_id = Column(
        String(32),
        ForeignKey("database_connections.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title = Column(String(255), nullable=False)
    current_sql_draft = Column(Text, nullable=True)
    sql_draft_version = Column(Integer, nullable=False, default=0)
    last_executed_sql = Column(Text, nullable=True)
    last_intent_json = Column(JSON, nullable=True)
    archived = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    messages = relationship(
        "ChatMessageModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessageModel.created_at",
    )
    executions = relationship(
        "QueryExecutionModel",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="QueryExecutionModel.created_at",
    )


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id = Column(String(32), primary_key=True, default=generate_id)
    session_id = Column(
        String(32),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(16), nullable=False)  # "user" | "assistant"
    text = Column(Text, nullable=False)
    structured_payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    session = relationship("ChatSessionModel", back_populates="messages")


class QueryExecutionModel(Base):
    __tablename__ = "chat_query_executions"

    id = Column(String(32), primary_key=True, default=generate_id)
    session_id = Column(
        String(32),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sql_text = Column(Text, nullable=False)
    columns_json = Column(JSON, nullable=True)
    rows_preview_json = Column(JSON, nullable=True)
    rows_preview_truncated = Column(Boolean, nullable=False, default=False)
    row_count = Column(Integer, nullable=False, default=0)
    execution_time_ms = Column(Integer, nullable=False, default=0)
    dataset_id = Column(String(32), nullable=True, unique=True, index=True)
    chart_recommendation_json = Column(JSON, nullable=True)
    analysis_message = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    session = relationship("ChatSessionModel", back_populates="executions")
    dataset = relationship(
        "DatasetModel",
        uselist=False,
        primaryjoin="QueryExecutionModel.dataset_id==DatasetModel.id",
        foreign_keys="QueryExecutionModel.dataset_id",
    )


class DatasetModel(Base):
    __tablename__ = "datasets"

    id = Column(String(32), primary_key=True, default=generate_id)
    name = Column(String(255), nullable=False)
    database_connection_id = Column(String(32), ForeignKey("database_connections.id"), nullable=False, index=True)
    source_type = Column(String(32), nullable=False, default="chat_execution")
    source_query_execution_id = Column(String(32), ForeignKey("chat_query_executions.id"), nullable=False, unique=True, index=True)
    sql = Column(Text, nullable=False)
    columns_schema = Column(JSON, nullable=False, default=list)
    preview_rows = Column(JSON, nullable=False, default=list)
    row_count = Column(Integer, nullable=False, default=0)
    created_by = Column(String(255), nullable=False, default="chat")
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)
    refresh_policy = Column(String(32), nullable=False, default="manual")
    last_refresh_at = Column(DateTime, nullable=True, index=True)

    source_query_execution = relationship(
        "QueryExecutionModel",
        uselist=False,
        foreign_keys="DatasetModel.source_query_execution_id",
    )
    widgets = relationship("WidgetModel", back_populates="dataset")


# ---------------------------------------------------------------------------
# Widgets & Dashboards
# ---------------------------------------------------------------------------

class WidgetModel(Base):
    __tablename__ = "widgets"

    id = Column(String(32), primary_key=True, default=generate_id)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(String(32), nullable=False, default="sql")  # "sql" | "text_to_sql" | "text"
    source_query_run_id = Column(String(32), nullable=True)
    dataset_id = Column(String(32), ForeignKey("datasets.id"), nullable=True, index=True)
    sql_text = Column(Text, nullable=False, default="")
    visualization_type = Column(String(32), nullable=False, default="table")  # table|line|bar|area|pie|metric|text
    visualization_config = Column(JSON, nullable=True)
    chart_spec_json = Column(JSON, nullable=True)
    result_schema = Column(JSON, nullable=True)
    refresh_policy = Column(String(32), nullable=False, default="on_view")  # manual|on_view|scheduled
    is_public = Column(Boolean, nullable=False, default=False)
    owner_id = Column(String(255), nullable=False, default="default")
    database_connection_id = Column(String(32), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    dashboard_widgets = relationship("DashboardWidgetModel", back_populates="widget", cascade="all, delete-orphan")
    runs = relationship("WidgetRunModel", back_populates="widget", cascade="all, delete-orphan", order_by="WidgetRunModel.started_at")
    dataset = relationship("DatasetModel", back_populates="widgets")


class WidgetRunModel(Base):
    __tablename__ = "widget_runs"

    id = Column(String(32), primary_key=True, default=generate_id)
    widget_id = Column(String(32), ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending")  # pending|running|completed|error
    columns_json = Column(JSON, nullable=True)
    rows_preview_json = Column(JSON, nullable=True)
    rows_preview_truncated = Column(Boolean, nullable=False, default=False)
    row_count = Column(Integer, nullable=False, default=0)
    execution_time_ms = Column(Integer, nullable=False, default=0)
    error_text = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=False, default=utcnow)
    finished_at = Column(DateTime, nullable=True)

    widget = relationship("WidgetModel", back_populates="runs")


class DashboardModel(Base):
    __tablename__ = "dashboards"

    id = Column(String(32), primary_key=True, default=generate_id)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    slug = Column(String(255), nullable=True, unique=True)
    layout_type = Column(String(32), nullable=False, default="grid")
    is_public = Column(Boolean, nullable=False, default=False)
    is_hidden = Column(Boolean, nullable=False, default=False)
    owner_id = Column(String(255), nullable=False, default="default")
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow, index=True)

    dashboard_widgets = relationship(
        "DashboardWidgetModel",
        back_populates="dashboard",
        cascade="all, delete-orphan",
        order_by="DashboardWidgetModel.created_at",
    )
    schedule = relationship("DashboardScheduleModel", back_populates="dashboard", uselist=False, cascade="all, delete-orphan")


class DashboardWidgetModel(Base):
    __tablename__ = "dashboard_widgets"

    id = Column(String(32), primary_key=True, default=generate_id)
    dashboard_id = Column(String(32), ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, index=True)
    widget_id = Column(String(32), ForeignKey("widgets.id", ondelete="CASCADE"), nullable=False, index=True)
    title_override = Column(String(255), nullable=True)
    layout = Column(JSON, nullable=False, default=lambda: {"x": 0, "y": 0, "w": 6, "h": 4})
    display_options = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    dashboard = relationship("DashboardModel", back_populates="dashboard_widgets")
    widget = relationship("WidgetModel", back_populates="dashboard_widgets")


class DashboardScheduleModel(Base):
    __tablename__ = "dashboard_schedules"

    id = Column(String(32), primary_key=True, default=generate_id)
    dashboard_id = Column(String(32), ForeignKey("dashboards.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    recipient_emails = Column(JSON, nullable=False, default=list)
    weekdays = Column(JSON, nullable=False, default=list)
    send_time = Column(String(5), nullable=False, default="09:00")
    timezone = Column(String(64), nullable=False, default="Europe/Moscow")
    enabled = Column(Boolean, nullable=False, default=False)
    subject = Column(String(255), nullable=False, default="Dashboard digest")
    last_sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    dashboard = relationship("DashboardModel", back_populates="schedule")
