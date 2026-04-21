from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.validation import SQLValidationAgent
from app.core.config import settings
from app.db.models import ChatSessionModel, QueryExecutionModel
from app.schemas.chat import ChartRecommendation
from app.services.chart_recommendation_service import ChartRecommendationService
from app.services.database_resolution import resolve_dialect, resolve_engine
from app.services.schema_context_provider import SchemaContextProvider


class ChatExecutionService:
    ROW_PREVIEW_LIMIT = 500
    ROW_PREVIEW_BYTE_LIMIT = 256 * 1024

    def __init__(self) -> None:
        self.validation_agent = SQLValidationAgent()
        self.chart_service = ChartRecommendationService()
        self.schema_provider = SchemaContextProvider()

    def execute(self, db: Session, session_id: str, sql: str) -> QueryExecutionModel:
        session = self._get_session(db, session_id)
        dialect = resolve_dialect(db, session.database_connection_id)
        engine = resolve_engine(db, session.database_connection_id)
        try:
            schema = self.schema_provider.get_schema_for_llm(db, session.database_connection_id)
        except Exception:  # noqa: BLE001
            schema = None
        validation = self.validation_agent.run(sql, dialect, schema=schema)
        if not validation.valid:
            raise ValueError("; ".join(validation.errors) or "SQL validation failed.")

        started_at = time.perf_counter()
        try:
            dataframe = self._read_dataframe(engine, validation.sql, dialect)
            execution_time_ms = int((time.perf_counter() - started_at) * 1000)
            columns = self._serialize_columns(dataframe)
            rows_full = json.loads(dataframe.to_json(orient="records", date_format="iso"))
            rows_preview, truncated = self._serialize_preview(rows_full)
            row_count = int(len(dataframe.index))
            chart_recommendation = self.chart_service.recommend(columns, rows_preview, row_count)

            execution = QueryExecutionModel(
                session_id=session.id,
                sql_text=validation.sql,
                columns_json=columns,
                rows_preview_json=rows_preview,
                rows_preview_truncated=truncated,
                row_count=row_count,
                execution_time_ms=execution_time_ms,
                chart_recommendation_json=chart_recommendation.model_dump(mode="json"),
                error_message=None,
            )
            session.last_executed_sql = validation.sql
            db.add(execution)
            db.commit()
            db.refresh(execution)
            return execution
        except Exception as exc:  # noqa: BLE001
            execution_time_ms = int((time.perf_counter() - started_at) * 1000)
            execution = QueryExecutionModel(
                session_id=session.id,
                sql_text=validation.sql,
                columns_json=None,
                rows_preview_json=None,
                rows_preview_truncated=False,
                row_count=0,
                execution_time_ms=execution_time_ms,
                chart_recommendation_json=None,
                error_message=str(exc),
            )
            session.last_executed_sql = validation.sql
            db.add(execution)
            db.commit()
            db.refresh(execution)
            return execution

    def _get_session(self, db: Session, session_id: str) -> ChatSessionModel:
        session = db.query(ChatSessionModel).filter(ChatSessionModel.id == session_id).first()
        if session is None:
            raise ValueError("Chat session not found.")
        return session

    def _read_dataframe(self, engine: Any, sql: str, dialect: str) -> pd.DataFrame:
        with engine.begin() as connection:
            self._apply_read_only_guards(connection, dialect)
            return pd.read_sql_query(text(sql), connection)

    def _apply_read_only_guards(self, connection: Any, dialect: str) -> None:
        if dialect.startswith("postgres"):
            timeout_ms = max(settings.query_timeout_seconds * 1000, 1000)
            connection.exec_driver_sql("SET LOCAL default_transaction_read_only = on")
            connection.exec_driver_sql(f"SET LOCAL statement_timeout = {timeout_ms}")
            return
        if dialect.startswith("mysql") or dialect.startswith("mariadb"):
            connection.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
            return
        if dialect.startswith("sqlite"):
            connection.exec_driver_sql("PRAGMA query_only = ON")
            return
        if dialect.startswith("clickhouse"):
            try:
                connection.exec_driver_sql("SET readonly = 1")
            except Exception:  # noqa: BLE001
                pass

    def _serialize_columns(self, dataframe: pd.DataFrame) -> list[dict[str, str]]:
        columns: list[dict[str, str]] = []
        for name in dataframe.columns:
            dtype = str(dataframe[name].dtype)
            columns.append({"name": str(name), "type": dtype})
        return columns

    def _serialize_preview(self, rows_full: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
        preview: list[dict[str, Any]] = []
        byte_size = 2
        truncated = False
        for row in rows_full:
            row_json = json.dumps(row, ensure_ascii=False, default=str)
            next_size = byte_size + len(row_json.encode("utf-8")) + (1 if preview else 0)
            if len(preview) >= self.ROW_PREVIEW_LIMIT or next_size > self.ROW_PREVIEW_BYTE_LIMIT:
                truncated = True
                break
            preview.append(row)
            byte_size = next_size
        if len(preview) < len(rows_full):
            truncated = True
        return preview, truncated
