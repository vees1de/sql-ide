from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from app.core.config import normalize_llm_model_alias, resolve_llm_model_from_alias
from app.agents.validation import SQLValidationAgent
from app.core.config import settings
from app.db.models import ChatMessageModel, ChatSessionModel, DatabaseConnectionModel, DatasetModel, QueryExecutionModel
from app.services.example_service import ExampleService
from app.schemas.chat import ChartRecommendation
from app.schemas.query import IntentPayload
from app.services.ai_chart_suggestion_service import AIChartSuggestionService
from app.services.chart_decision_service import ChartDecisionService
from app.services.chart_spec_service import ChartSpecService
from app.services.database_resolution import resolve_allowed_tables, resolve_dialect, resolve_engine
from app.services.llm_schema_recon_service import LLMSchemaReconService
from app.services.llm_service import LLMService
from app.services.schema_context_provider import SchemaContextProvider
from app.services.semantic_catalog_service import SemanticCatalogService


class ChatExecutionService:
    ROW_PREVIEW_LIMIT = 500
    ROW_PREVIEW_BYTE_LIMIT = 256 * 1024
    MAX_REPAIR_ATTEMPTS = 2

    def __init__(self) -> None:
        self.validation_agent = SQLValidationAgent()
        self.chart_service = ChartDecisionService()
        self.chart_spec_service = ChartSpecService()
        self.ai_chart_suggestion_service = AIChartSuggestionService()
        self.schema_provider = SchemaContextProvider()
        self.llm_service = LLMService()
        self.schema_recon_service = LLMSchemaReconService()
        self.semantic_catalog_service = SemanticCatalogService()
        self.example_service = ExampleService()

    def execute(self, db: Session, session_id: str, sql: str) -> QueryExecutionModel:
        session = self._get_session(db, session_id)
        database_connection = self._get_database_connection(db, session.database_connection_id)
        dialect = resolve_dialect(db, session.database_connection_id)
        engine = resolve_engine(db, session.database_connection_id)
        allowed_tables = resolve_allowed_tables(db, session.database_connection_id, engine)
        self._check_execution_permissions(database_connection)
        try:
            schema = self.schema_provider.get_schema_for_llm(db, session.database_connection_id)
        except Exception:  # noqa: BLE001
            schema = None
        try:
            semantic_catalog = self.semantic_catalog_service.load_catalog(db, session.database_connection_id)
        except Exception:  # noqa: BLE001
            semantic_catalog = None
        repair_context = self._build_repair_context(db, session, schema)
        attempted_sql = sql
        repair_attempt = 0

        while True:
            validation = self.validation_agent.run(
                attempted_sql,
                dialect,
                allowed_tables=allowed_tables,
                schema=schema,
                semantic_catalog=semantic_catalog,
            )
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
                self._dry_run_query(engine, validation.sql, dialect)
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
                chart_spec = self.chart_spec_service.from_decision(
                    execution_result,
                    decision,
                    title="Автоматическая визуализация",
                )
                chart_payload = chart_spec.data
                chart_recommendation = ChartRecommendation(
                    recommended_view="chart" if decision.chart_type != "table" else "table",
                    chart_type=decision.chart_type if decision.chart_type != "table" else None,
                    x=decision.encoding.x_field,
                    y=decision.encoding.y_field,
                    series=decision.encoding.series_field,
                    facet=decision.encoding.facet_field,
                    variant=decision.variant,
                    explanation=decision.explanation,
                    rule_id=decision.rule_id,
                    confidence=decision.confidence,
                    data=chart_payload,
                    reason=decision.reason,
                    semantic_intent=decision.semantic_intent,
                    analysis_mode=decision.analysis_mode,
                    visual_goal=decision.visual_goal,
                    time_role=decision.time_role,
                    comparison_goal=decision.comparison_goal,
                    preferred_mark=decision.preferred_mark,
                    normalize=decision.encoding.normalize,
                    value_format=decision.encoding.value_format,
                    series_limit=decision.encoding.series_limit,
                    category_limit=decision.encoding.category_limit,
                    top_n_strategy=decision.encoding.top_n_strategy,
                    alternatives=list(decision.alternatives),
                    candidates=list(decision.candidates),
                    constraints_applied=list(decision.constraints_applied),
                    visual_load=decision.visual_load,
                    query_interpretation=decision.query_interpretation,
                    decision_summary=decision.decision_summary,
                    reason_codes=list(decision.reason_codes),
                    chart_spec=chart_spec,
                    ai_chart_spec=None,
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
                db.flush()
                dataset = self._create_dataset(
                    execution=execution,
                    session=session,
                    sql=validation.sql,
                    columns=columns,
                    preview_rows=rows_preview,
                    row_count=row_count,
                )
                db.add(dataset)
                db.flush()
                execution.dataset_id = dataset.id
                db.commit()
                db.refresh(execution)
                # Auto-save only direct, successful SQL drafts to avoid polluting RAG
                # with repaired or clarification-derived queries.
                if row_count > 0 and self._should_store_rag_example(session.messages, attempted_sql, validation.sql):
                    user_prompt = self._latest_user_prompt(session.messages)
                    if user_prompt and session.database_connection_id:
                        try:
                            self.example_service.save_example(
                                db,
                                session.database_connection_id,
                                user_prompt,
                                validation.sql,
                                source="auto",
                            )
                        except Exception:  # noqa: BLE001
                            pass
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

    def execute_prepared(self, db: Session, session_id: str, sql: str | None = None) -> QueryExecutionModel:
        session = self._get_session(db, session_id)
        latest_payload = self._latest_assistant_payload(session.messages)
        prepared_sql = str(sql or session.current_sql_draft or "").strip()
        if not prepared_sql:
            raise ValueError("No prepared SQL found for this session.")

        state = str(latest_payload.get("state") or "")
        actions = latest_payload.get("actions") or []
        has_run_action = any(str((action or {}).get("type") or "") == "show_run_button" for action in actions)
        if state != "SQL_READY" and not has_run_action:
            raise ValueError("Prepared SQL is not ready to run yet.")

        return self.execute(db, session_id, prepared_sql)

    def suggest_chart(self, db: Session, session_id: str, execution_id: str, goal: str = "best_chart") -> QueryExecutionModel:
        execution = self._get_execution(db, session_id, execution_id)
        if execution.error_message:
            raise ValueError("Chart suggestion is unavailable for failed executions.")
        if not execution.rows_preview_json or not execution.columns_json:
            raise ValueError("Chart suggestion requires a successful query result.")

        execution_result = self._build_execution_result(
            execution.sql_text,
            execution.rows_preview_json,
            execution.columns_json,
            execution.row_count,
            execution.execution_time_ms,
        )
        chart_spec = self.ai_chart_suggestion_service.suggest(
            goal=goal,
            sql=execution.sql_text,
            columns=execution.columns_json,
            execution=execution_result,
        )

        chart_recommendation_json = dict(execution.chart_recommendation_json or {})
        chart_recommendation_json["ai_chart_spec"] = chart_spec.model_dump(mode="json")
        execution.chart_recommendation_json = chart_recommendation_json
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

    def _get_database_connection(self, db: Session, database_connection_id: str) -> DatabaseConnectionModel | None:
        return (
            db.query(DatabaseConnectionModel)
            .filter(DatabaseConnectionModel.id == database_connection_id)
            .first()
        )

    def _get_execution(self, db: Session, session_id: str, execution_id: str) -> QueryExecutionModel:
        execution = (
            db.query(QueryExecutionModel)
            .filter(
                QueryExecutionModel.id == execution_id,
                QueryExecutionModel.session_id == session_id,
            )
            .first()
        )
        if execution is None:
            raise ValueError("Query execution not found.")
        return execution

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

    def _should_store_rag_example(
        self,
        messages: list[ChatMessageModel],
        attempted_sql: str,
        executed_sql: str,
    ) -> bool:
        payload = self._latest_assistant_payload(messages)
        if not payload or not bool(payload.get("rag_example_candidate")):
            return False
        draft_sql = str(payload.get("sql") or "").strip()
        if not draft_sql:
            return False
        if self._normalize_sql_text(draft_sql) != self._normalize_sql_text(executed_sql):
            return False
        if self._normalize_sql_text(attempted_sql) != self._normalize_sql_text(executed_sql):
            return False
        return True

    @staticmethod
    def _normalize_sql_text(sql: str) -> str:
        return " ".join(str(sql or "").split()).strip().lower()

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

    def _check_execution_permissions(self, database_connection: DatabaseConnectionModel | None) -> None:
        if database_connection is None:
            return
        read_only_value = str(database_connection.read_only or "").strip().lower()
        if read_only_value in {"false", "0", "no"}:
            raise ValueError("Chat execution is allowed only for read-only database connections.")

    def _dry_run_query(self, engine: Any, sql: str, dialect: str) -> None:
        with engine.begin() as connection:
            self._apply_read_only_guards(connection, dialect)
            connection.execute(text(f"SELECT * FROM ({sql}) AS __codex_dry_run LIMIT 0"))

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

    def _create_dataset(
        self,
        *,
        execution: QueryExecutionModel,
        session: ChatSessionModel,
        sql: str,
        columns: list[dict[str, str]],
        preview_rows: list[dict[str, Any]],
        row_count: int,
    ) -> DatasetModel:
        title = (session.title or "").strip() or "Dataset"
        if len(title) > 255:
            title = title[:252] + "..."

        return DatasetModel(
            name=title,
            database_connection_id=session.database_connection_id,
            source_type="chat_execution",
            source_query_execution_id=execution.id,
            sql=sql,
            columns_schema=columns,
            preview_rows=preview_rows,
            row_count=row_count,
            created_by=f"chat_session:{session.id}",
            created_at=datetime.utcnow(),
            refresh_policy="manual",
            last_refresh_at=datetime.utcnow(),
        )

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
