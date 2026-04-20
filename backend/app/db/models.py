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
    chart_recommendation_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow, index=True)

    session = relationship("ChatSessionModel", back_populates="executions")
