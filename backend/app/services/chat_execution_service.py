from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.core.config import normalize_llm_model_alias, resolve_llm_model_from_alias
from app.agents.validation import SQLValidationAgent
from app.core.config import settings
from app.db.models import ChatMessageModel, ChatSessionModel, QueryExecutionModel
from app.schemas.chat import ChartRecommendation
from app.schemas.query import IntentPayload
from app.services.chart_data_adapter import ChartDataAdapter
from app.services.chart_decision_service import ChartDecisionService
from app.services.database_resolution import resolve_dialect, resolve_engine
from app.services.llm_schema_recon_service import LLMSchemaReconService
from app.services.llm_service import LLMService
from app.services.schema_context_provider import SchemaContextProvider


class ChatExecutionService:
    ROW_PREVIEW_LIMIT = 500
    ROW_PREVIEW_BYTE_LIMIT = 256 * 1024
    MAX_REPAIR_ATTEMPTS = 2

    def __init__(self) -> None:
        self.validation_agent = SQLValidationAgent()
        self.chart_service = ChartDecisionService()
        self.chart_data_adapter = ChartDataAdapter()
        self.schema_provider = SchemaContextProvider()
        self.llm_service = LLMService()
        self.schema_recon_service = LLMSchemaReconService()

    def execute(self, db: Session, session_id: str, sql: str) -> QueryExecutionModel:
        session = self._get_session(db, session_id)
        dialect = resolve_dialect(db, session.database_connection_id)
        engine = resolve_engine(db, session.database_connection_id)
        try:
            schema = self.schema_provider.get_schema_for_llm(db, session.database_connection_id)
        except Exception:  # noqa: BLE001
            schema = None
        repair_context = self._build_repair_context(db, session, schema)
        attempted_sql = sql
        repair_attempt = 0

        while True:
            validation = self.validation_agent.run(attempted_sql, dialect, schema=schema)
            if not validation.valid:
                repaired_sql = self._attempt_repair(
                    repair_context,
                    schema=schema,
                    failed_sql=attempted_sql,
                    failure_reason="; ".join(validation.errors) or "SQL validation failed.",
                    attempt_index=repair_attempt,
                    row_count=None,
                    execution_columns=[],
                    execution_rows=[],
                )
                if repaired_sql is not None:
                    attempted_sql = repaired_sql
                    repair_attempt += 1
                    continue
                raise ValueError("; ".join(validation.errors) or "SQL validation failed.")

            started_at = time.perf_counter()
            try:
                dataframe = self._read_dataframe(engine, validation.sql, dialect)
                execution_time_ms = int((time.perf_counter() - started_at) * 1000)
                columns = self._serialize_columns(dataframe)
                rows_full = json.loads(dataframe.to_json(orient="records", date_format="iso"))
                rows_preview, truncated = self._serialize_preview(rows_full)
                row_count = int(len(dataframe.index))

                if row_count == 0:
                    repaired_sql = self._attempt_repair(
                        repair_context,
                        schema=schema,
                        failed_sql=validation.sql,
                        failure_reason="SQL executed successfully but returned 0 rows.",
                        attempt_index=repair_attempt,
                        row_count=row_count,
                        execution_columns=[str(column.get("name")) for column in columns],
                        execution_rows=rows_preview,
                    )
                    if repaired_sql is not None:
                        attempted_sql = repaired_sql
                        repair_attempt += 1
                        continue

                execution_result = self._build_execution_result(validation.sql, rows_preview, columns, row_count, execution_time_ms)
                decision = self.chart_service.decide(None, execution_result)
                chart_payload = self.chart_data_adapter.build(execution_result, decision)
                chart_recommendation = ChartRecommendation(
                    recommended_view="chart" if decision.chart_type != "table" else "table",
                    chart_type=decision.chart_type if decision.chart_type != "table" else None,
                    x=decision.encoding.x_field,
                    y=decision.encoding.y_field,
                    series=decision.encoding.series_field,
                    variant=decision.variant,
                    explanation=decision.explanation,
                    rule_id=decision.rule_id,
                    confidence=decision.confidence,
                    data=chart_payload,
                    reason=decision.explanation,
                )

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
                if validation.sql.strip() != (sql or "").strip():
                    session.current_sql_draft = validation.sql
                    session.sql_draft_version = (session.sql_draft_version or 0) + 1
                db.add(execution)
                db.commit()
                db.refresh(execution)
                return execution
            except Exception as exc:  # noqa: BLE001
                execution_time_ms = int((time.perf_counter() - started_at) * 1000)
                repaired_sql = self._attempt_repair(
                    repair_context,
                    schema=schema,
                    failed_sql=validation.sql,
                    failure_reason=str(exc),
                    attempt_index=repair_attempt,
                    row_count=None,
                    execution_columns=[],
                    execution_rows=[],
                )
                if repaired_sql is not None:
                    attempted_sql = repaired_sql
                    repair_attempt += 1
                    continue
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
        session = (
            db.query(ChatSessionModel)
            .options(
                selectinload(ChatSessionModel.messages),
                selectinload(ChatSessionModel.executions),
            )
            .filter(ChatSessionModel.id == session_id)
            .first()
        )
        if session is None:
            raise ValueError("Chat session not found.")
        return session

    def _build_repair_context(self, db: Session, session: ChatSessionModel, schema: Any | None) -> dict[str, Any]:
        assistant_payload = self._latest_assistant_payload(session.messages)
        model_alias = normalize_llm_model_alias(assistant_payload.get("llm_model_alias")) if assistant_payload.get("llm_model_alias") else None
        query_mode = str(assistant_payload.get("query_mode") or "fast")
        previous_intent = self._load_previous_intent(session.last_intent_json)
        toolbox = None
        if query_mode == "thinking":
            toolbox = self.schema_recon_service.build_toolbox(db, session.database_connection_id)
        return {
            "prompt": self._latest_user_prompt(session.messages),
            "history_text": self._build_history_text(session.messages),
            "previous_intent": previous_intent,
            "llm_model": resolve_llm_model_from_alias(model_alias) if model_alias else settings.llm_model,
            "query_mode": query_mode,
            "schema_toolbox": toolbox,
            "schema": schema,
        }

    def _attempt_repair(
        self,
        repair_context: dict[str, Any],
        *,
        schema: Any | None,
        failed_sql: str,
        failure_reason: str,
        attempt_index: int,
        row_count: int | None,
        execution_columns: list[str],
        execution_rows: list[dict[str, Any]],
    ) -> str | None:
        if attempt_index >= self.MAX_REPAIR_ATTEMPTS:
            return None
        if repair_context.get("query_mode") != "thinking":
            return None
        prompt = str(repair_context.get("prompt") or "").strip()
        model = repair_context.get("llm_model")
        if not prompt or not model or schema is None:
            return None

        payload = self.llm_service.repair_sql(
            prompt=prompt,
            schema=schema,
            failed_sql=failed_sql,
            failure_reason=failure_reason,
            previous_intent=repair_context.get("previous_intent"),
            history_text=repair_context.get("history_text"),
            row_count=row_count,
            execution_columns=execution_columns,
            execution_rows=execution_rows,
            attempt_index=attempt_index + 1,
            model=model,
            schema_toolbox=repair_context.get("schema_toolbox"),
        )
        if payload is None or not payload.retryable or not payload.sql:
            return None
        repaired_sql = str(payload.sql).strip()
        if not repaired_sql or repaired_sql == failed_sql.strip():
            return None
        return repaired_sql

    def _latest_assistant_payload(self, messages: list[ChatMessageModel]) -> dict[str, Any]:
        for message in reversed(messages):
            if message.role != "assistant":
                continue
            payload = getattr(message, "structured_payload", None)
            if isinstance(payload, dict):
                return payload
        return {}

    def _latest_user_prompt(self, messages: list[ChatMessageModel]) -> str:
        for message in reversed(messages):
            if message.role == "user" and str(message.text or "").strip():
                return str(message.text).strip()
        return ""

    def _build_history_text(self, messages: list[ChatMessageModel]) -> str:
        recent_messages = messages[-6:]
        lines: list[str] = []
        for message in recent_messages:
            role = "user" if message.role == "user" else "assistant"
            lines.append(f"[{role}] {str(message.text or '').strip()}")
        return "\n".join(lines)

    def _load_previous_intent(self, payload: Any | None) -> IntentPayload | None:
        if not isinstance(payload, dict):
            return None
        try:
            return IntentPayload.model_validate(payload)
        except Exception:  # noqa: BLE001
            return None

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

    def _build_execution_result(
        self,
        sql: str,
        rows: list[dict[str, Any]],
        columns: list[dict[str, str]],
        row_count: int,
        execution_time_ms: int,
    ):
        from app.schemas.query import QueryExecutionResult

        return QueryExecutionResult(
            sql=sql,
            rows=rows,
            columns=[str(column.get("name")) for column in columns],
            row_count=row_count,
            execution_time_ms=execution_time_ms,
        )
