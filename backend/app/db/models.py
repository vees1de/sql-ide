from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
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
