from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agents.clarification import ClarificationAgent
from app.agents.insight import InsightAgent
from app.agents.intent import IntentAgent
from app.agents.semantic import SemanticMappingAgent
from app.agents.sql_generation import SQLGenerationAgent
from app.agents.validation import SQLValidationAgent
from app.agents.visualization import VisualizationAgent
from app.core.config import settings
from app.db.models import (
    CellModel,
    DatabaseConnectionModel,
    NotebookModel,
    QueryRunModel,
    SemanticDictionaryModel,
)
from app.db.session import analytics_engine
from app.schemas.query import (
    ChartEncoding,
    ChartSpec,
    IntentPayload,
    PromptRunResponse,
    QueryExecutionResult,
)
from app.services.analytics import AnalyticsExecutionService
from app.services.llm_service import LLMQueryPlan, LLMService
from app.services.metadata_service import MetadataService
from app.services.notebook_service import NotebookService


class QueryOrchestrationService:
    def __init__(self) -> None:
        self.intent_agent = IntentAgent()
        self.semantic_agent = SemanticMappingAgent()
        self.sql_generation_agent = SQLGenerationAgent()
        self.validation_agent = SQLValidationAgent()
        self.visualization_agent = VisualizationAgent()
        self.insight_agent = InsightAgent()
        self.clarification_agent = ClarificationAgent()
        self.analytics_service = AnalyticsExecutionService()
        self.notebook_service = NotebookService()
        self.metadata_service = MetadataService()
        self.llm_service = LLMService()

    def run_prompt(
        self,
        db: Session,
        notebook: NotebookModel,
        prompt: str,
        existing_prompt_cell: CellModel | None = None,
    ) -> PromptRunResponse:
        previous_intent = self._load_previous_intent(db, notebook.id)
        prompt_cell = existing_prompt_cell or self._create_prompt_cell(db, notebook, prompt)

        llm_response = self._run_prompt_with_llm(
            db=db,
            notebook=notebook,
            prompt=prompt,
            prompt_cell=prompt_cell,
            previous_intent=previous_intent,
        )
        if llm_response is not None:
            return llm_response

        return self._run_prompt_with_rules(
            db=db,
            notebook=notebook,
            prompt=prompt,
            prompt_cell=prompt_cell,
            previous_intent=previous_intent,
        )

    def rerun_notebook(self, db: Session, notebook: NotebookModel) -> list[PromptRunResponse]:
        input_cells = self.notebook_service.list_input_cells(notebook)
        self.notebook_service.delete_generated_runs(db, notebook)
        db.flush()

        responses: list[PromptRunResponse] = []
        for input_cell in input_cells:
            if input_cell.type == "prompt":
                prompt_text = str(input_cell.content.get("text", "")).strip()
                if prompt_text:
                    responses.append(self.run_prompt(db, notebook, prompt_text, existing_prompt_cell=input_cell))
            elif input_cell.type == "sql":
                sql = str(input_cell.content.get("sql", "")).strip()
                if sql:
                    responses.append(self.run_sql_cell(db, notebook, input_cell))
            db.refresh(notebook)
        return responses

    def run_sql_cell(
        self,
        db: Session,
        notebook: NotebookModel,
        sql_cell: CellModel,
    ) -> PromptRunResponse:
        sql = str(sql_cell.content.get("sql", "")).strip()
        if not sql:
            return self._persist_manual_sql_error_run(
                db=db,
                notebook=notebook,
                sql_cell=sql_cell,
                validation={
                    "sql": "",
                    "errors": ["SQL cell is empty."],
                    "warnings": [],
                },
            )

        dialect = self._resolve_dialect(db, notebook)
        validation = self.validation_agent.run(
            sql,
            dialect,
            allowed_tables=self._resolve_allowed_tables(db, notebook),
        )
        if not validation.valid:
            return self._persist_manual_sql_error_run(
                db=db,
                notebook=notebook,
                sql_cell=sql_cell,
                validation=validation.model_dump(mode="json"),
            )

        try:
            execution = self.analytics_service.execute(validation.sql)
        except Exception as exc:  # noqa: BLE001
            return self._persist_manual_sql_error_run(
                db=db,
                notebook=notebook,
                sql_cell=sql_cell,
                validation={
                    "sql": validation.sql,
                    "errors": [f"Execution error: {exc}"],
                    "warnings": validation.warnings,
                },
            )

        sql_cell.content = {
            "sql": validation.sql,
            "warnings": validation.warnings,
        }
        chart_spec = self._build_manual_chart_spec(execution)
        insight_text = self.llm_service.summarize_result(
            prompt="Manual SQL cell",
            sql=validation.sql,
            columns=execution.columns,
            rows=execution.rows,
            row_count=execution.row_count,
        ) or self._build_generic_insight(execution, chart_spec)

        return self._persist_success_run(
            db=db,
            notebook=notebook,
            prompt=validation.sql,
            prompt_cell=sql_cell,
            validation=validation.model_dump(mode="json"),
            execution=execution.model_dump(mode="json"),
            chart_spec=chart_spec.model_dump(mode="json"),
            insight_text=insight_text,
            explanation={
                "source": "manual_sql",
                "warnings": validation.warnings,
            },
            agent_trace={
                "plan_source": "manual_sql",
                "validation": validation.model_dump(mode="json"),
                "chart_spec": chart_spec.model_dump(mode="json"),
                "preview_rows": execution.rows[:5],
            },
            confidence=1.0,
            include_sql_cell=False,
        )

    def _run_prompt_with_llm(
        self,
        db: Session,
        notebook: NotebookModel,
        prompt: str,
        prompt_cell: CellModel,
        previous_intent: IntentPayload | None,
    ) -> PromptRunResponse | None:
        if not self.llm_service.configured:
            return None

        schema = self.metadata_service.get_schema()
        allowed_tables = [table.name for table in schema.tables]
        plan = self.llm_service.plan_query(prompt=prompt, schema=schema, previous_intent=previous_intent)
        if plan is None:
            return None

        intent = plan.intent
        if intent.clarification_question and not plan.sql:
            schema = self.metadata_service.get_schema()
            clarification_payload = self.clarification_agent.run(intent, schema=schema)
            clarification_payload["question"] = intent.clarification_question or clarification_payload.get("question")
            return self._persist_clarification_run(
                db=db,
                notebook=notebook,
                prompt_cell=prompt_cell,
                intent=intent,
                clarification=clarification_payload,
            )

        if not plan.sql:
            return None

        validation = self.validation_agent.run(plan.sql, schema.dialect, allowed_tables=allowed_tables)
        if not validation.valid:
            if settings.analytics_uses_demo_data:
                return None
            return self._persist_error_run(
                db=db,
                notebook=notebook,
                prompt_cell=prompt_cell,
                prompt=prompt,
                intent=intent,
                validation=validation.model_dump(mode="json"),
            )

        try:
            execution = self.analytics_service.execute(validation.sql)
        except Exception as exc:  # noqa: BLE001
            if settings.analytics_uses_demo_data:
                return None
            return self._persist_error_run(
                db=db,
                notebook=notebook,
                prompt_cell=prompt_cell,
                prompt=prompt,
                intent=intent,
                validation={
                    "sql": validation.sql,
                    "errors": [f"Execution error: {exc}"],
                    "warnings": validation.warnings,
                },
            )

        chart_spec = self._build_chart_spec(prompt, plan, execution)
        insight_text = self.llm_service.summarize_result(
            prompt=prompt,
            sql=validation.sql,
            columns=execution.columns,
            rows=execution.rows,
            row_count=execution.row_count,
        ) or self._build_generic_insight(execution, chart_spec)

        explanation = {
            "metric": intent.metric,
            "dimensions": intent.dimensions,
            "filters": [item.model_dump(mode="json") for item in intent.filters],
            "comparison": intent.comparison,
            "warnings": list(dict.fromkeys(plan.warnings + validation.warnings)),
            "source": "llm",
        }
        agent_trace = {
            "plan_source": "llm",
            "intent": intent.model_dump(mode="json"),
            "llm_plan": plan.model_dump(mode="json"),
            "validation": validation.model_dump(mode="json"),
            "chart_spec": chart_spec.model_dump(mode="json"),
            "preview_rows": execution.rows[:5],
        }

        return self._persist_success_run(
            db=db,
            notebook=notebook,
            prompt=prompt,
            prompt_cell=prompt_cell,
            validation=validation.model_dump(mode="json"),
            execution=execution.model_dump(mode="json"),
            chart_spec=chart_spec.model_dump(mode="json"),
            insight_text=insight_text,
            explanation=explanation,
            agent_trace=agent_trace,
            confidence=intent.confidence,
        )

    def _run_prompt_with_rules(
        self,
        db: Session,
        notebook: NotebookModel,
        prompt: str,
        prompt_cell: CellModel,
        previous_intent: IntentPayload | None,
    ) -> PromptRunResponse:
        intent = self.intent_agent.run(prompt=prompt, previous_intent=previous_intent)

        if intent.clarification_question and intent.metric is None:
            return self._persist_clarification_run(db, notebook, prompt_cell, intent)

        dictionary_entries = self._load_dictionary(db)
        semantic = self.semantic_agent.run(
            intent=intent,
            dictionary_entries=dictionary_entries,
            dialect=analytics_engine.dialect.name,
        )
        sql = self.sql_generation_agent.run(intent, semantic)
        validation = self.validation_agent.run(
            sql,
            semantic.dialect,
            allowed_tables=self.metadata_service.list_table_names(),
        )

        if not validation.valid:
            return self._persist_error_run(
                db=db,
                notebook=notebook,
                prompt_cell=prompt_cell,
                prompt=prompt,
                intent=intent,
                validation=validation.model_dump(mode="json"),
            )

        try:
            execution = self.analytics_service.execute(validation.sql)
        except Exception as exc:  # noqa: BLE001
            return self._persist_error_run(
                db=db,
                notebook=notebook,
                prompt_cell=prompt_cell,
                prompt=prompt,
                intent=intent,
                validation={
                    "sql": validation.sql,
                    "errors": [f"Execution error: {exc}"],
                    "warnings": validation.warnings,
                },
            )
        chart_spec = self.visualization_agent.run(intent, semantic, execution)
        insight_text = self.insight_agent.run(intent, semantic, execution)

        explanation = self._build_explanation(intent, semantic)
        agent_trace = {
            "plan_source": "rules",
            "intent": intent.model_dump(mode="json"),
            "semantic_mapping": semantic.model_dump(mode="json"),
            "validation": validation.model_dump(mode="json"),
            "chart_spec": chart_spec.model_dump(mode="json"),
            "preview_rows": execution.rows[:5],
        }

        return self._persist_success_run(
            db=db,
            notebook=notebook,
            prompt=prompt,
            prompt_cell=prompt_cell,
            validation=validation.model_dump(mode="json"),
            execution=execution.model_dump(mode="json"),
            chart_spec=chart_spec.model_dump(mode="json"),
            insight_text=insight_text,
            explanation=explanation,
            agent_trace=agent_trace,
            confidence=intent.confidence,
        )

    def _persist_success_run(
        self,
        db: Session,
        notebook: NotebookModel,
        prompt: str,
        prompt_cell: CellModel,
        validation: dict[str, Any],
        execution: dict[str, Any],
        chart_spec: dict[str, Any],
        insight_text: str,
        explanation: dict[str, Any],
        agent_trace: dict[str, Any],
        confidence: float,
        include_sql_cell: bool = True,
    ) -> PromptRunResponse:
        query_run = QueryRunModel(
            notebook_id=notebook.id,
            prompt_cell_id=prompt_cell.id,
            prompt_text=prompt,
            sql=validation["sql"],
            explanation=explanation,
            agent_trace=agent_trace,
            confidence=confidence,
            execution_time_ms=execution["execution_time_ms"],
            row_count=execution["row_count"],
            status="success",
        )
        db.add(query_run)
        db.flush()

        generated_cells = self._create_success_cells(
            db=db,
            notebook=notebook,
            query_run=query_run,
            validation=validation,
            execution=execution,
            chart_spec=chart_spec,
            insight_text=insight_text,
            include_sql_cell=include_sql_cell,
        )
        notebook.status = "saved"
        self.notebook_service.touch_notebook(notebook)
        db.commit()

        return PromptRunResponse(
            notebook_id=notebook.id,
            query_run_id=query_run.id,
            prompt_cell_id=prompt_cell.id,
            generated_cell_ids=[cell.id for cell in generated_cells],
            status=query_run.status,
        )

    def _load_previous_intent(self, db: Session, notebook_id: str) -> IntentPayload | None:
        previous_intent = self.notebook_service.get_last_successful_intent(db, notebook_id)
        if previous_intent is None:
            return None
        try:
            return IntentPayload.model_validate(previous_intent)
        except ValidationError:
            return None

    def _load_dictionary(self, db: Session) -> list[SemanticDictionaryModel]:
        return db.query(SemanticDictionaryModel).order_by(SemanticDictionaryModel.term.asc()).all()

    def _create_prompt_cell(self, db: Session, notebook: NotebookModel, prompt: str) -> CellModel:
        prompt_cell = CellModel(
            notebook_id=notebook.id,
            type="prompt",
            position=self.notebook_service.next_cell_position(notebook),
            content={"text": prompt},
        )
        db.add(prompt_cell)
        db.flush()
        notebook.cells.append(prompt_cell)
        self.notebook_service.touch_notebook(notebook)
        return prompt_cell

    def _persist_clarification_run(
        self,
        db: Session,
        notebook: NotebookModel,
        prompt_cell: CellModel,
        intent: IntentPayload,
        clarification: dict[str, Any] | None = None,
    ) -> PromptRunResponse:
        clarification_payload = clarification or self.clarification_agent.run(
            intent, schema=self.metadata_service.get_schema()
        )
        query_run = QueryRunModel(
            notebook_id=notebook.id,
            prompt_cell_id=prompt_cell.id,
            prompt_text=intent.raw_prompt,
            sql="",
            explanation={"status": "clarification_required"},
            agent_trace={"intent": intent.model_dump(mode="json"), "clarification": clarification_payload},
            confidence=intent.confidence,
            execution_time_ms=0,
            row_count=0,
            status="clarification_required",
        )
        db.add(query_run)
        db.flush()

        clarification_cell = CellModel(
            notebook_id=notebook.id,
            query_run_id=query_run.id,
            type="clarification",
            position=self.notebook_service.next_cell_position(notebook),
            content=clarification_payload,
        )
        db.add(clarification_cell)
        notebook.cells.append(clarification_cell)
        self.notebook_service.touch_notebook(notebook)
        db.commit()

        return PromptRunResponse(
            notebook_id=notebook.id,
            query_run_id=query_run.id,
            prompt_cell_id=prompt_cell.id,
            generated_cell_ids=[clarification_cell.id],
            status=query_run.status,
        )

    def _persist_error_run(
        self,
        db: Session,
        notebook: NotebookModel,
        prompt_cell: CellModel,
        prompt: str,
        intent: IntentPayload,
        validation: dict[str, Any],
    ) -> PromptRunResponse:
        query_run = QueryRunModel(
            notebook_id=notebook.id,
            prompt_cell_id=prompt_cell.id,
            prompt_text=prompt,
            sql=validation.get("sql", ""),
            explanation={"status": "error"},
            agent_trace={"intent": intent.model_dump(mode="json"), "validation": validation},
            confidence=intent.confidence,
            execution_time_ms=0,
            row_count=0,
            status="error",
            error_message="; ".join(validation.get("errors") or ["SQL validation failed."]),
        )
        db.add(query_run)
        db.flush()

        error_cell = CellModel(
            notebook_id=notebook.id,
            query_run_id=query_run.id,
            type="clarification",
            position=self.notebook_service.next_cell_position(notebook),
            content={
                "question": "Не удалось безопасно выполнить запрос.",
                "errors": validation.get("errors", []),
                "warnings": validation.get("warnings", []),
            },
        )
        db.add(error_cell)
        notebook.cells.append(error_cell)
        self.notebook_service.touch_notebook(notebook)
        db.commit()

        return PromptRunResponse(
            notebook_id=notebook.id,
            query_run_id=query_run.id,
            prompt_cell_id=prompt_cell.id,
            generated_cell_ids=[error_cell.id],
            status=query_run.status,
        )

    def _create_success_cells(
        self,
        db: Session,
        notebook: NotebookModel,
        query_run: QueryRunModel,
        validation: dict[str, Any],
        execution: dict[str, Any],
        chart_spec: dict[str, Any],
        insight_text: str,
        include_sql_cell: bool = True,
    ) -> list[CellModel]:
        base_position = self.notebook_service.next_cell_position(notebook)
        cells: list[CellModel] = []

        if include_sql_cell:
            cells.append(
                CellModel(
                    notebook_id=notebook.id,
                    query_run_id=query_run.id,
                    type="sql",
                    position=base_position,
                    content={
                        "sql": validation["sql"],
                        "warnings": validation.get("warnings", []),
                    },
                )
            )

        result_offset = 1 if include_sql_cell else 0
        cells.extend(
            [
                CellModel(
                    notebook_id=notebook.id,
                    query_run_id=query_run.id,
                    type="table",
                    position=base_position + result_offset,
                    content={
                        "columns": execution["columns"],
                        "rows": execution["rows"],
                        "rowCount": execution["row_count"],
                    },
                ),
                CellModel(
                    notebook_id=notebook.id,
                    query_run_id=query_run.id,
                    type="chart",
                    position=base_position + result_offset + 1,
                    content={
                        "chartSpec": chart_spec,
                        "data": execution["rows"],
                    },
                ),
                CellModel(
                    notebook_id=notebook.id,
                    query_run_id=query_run.id,
                    type="insight",
                    position=base_position + result_offset + 2,
                    content={"text": insight_text},
                ),
            ]
        )
        for cell in cells:
            db.add(cell)
            notebook.cells.append(cell)
        db.flush()
        return cells

    def _persist_manual_sql_error_run(
        self,
        db: Session,
        notebook: NotebookModel,
        sql_cell: CellModel,
        validation: dict[str, Any],
    ) -> PromptRunResponse:
        query_run = QueryRunModel(
            notebook_id=notebook.id,
            prompt_cell_id=sql_cell.id,
            prompt_text=str(sql_cell.content.get("sql", "")),
            sql=validation.get("sql", ""),
            explanation={"status": "error", "source": "manual_sql"},
            agent_trace={"plan_source": "manual_sql", "validation": validation},
            confidence=1.0,
            execution_time_ms=0,
            row_count=0,
            status="error",
            error_message="; ".join(validation.get("errors") or ["SQL validation failed."]),
        )
        db.add(query_run)
        db.flush()

        error_cell = CellModel(
            notebook_id=notebook.id,
            query_run_id=query_run.id,
            type="clarification",
            position=self.notebook_service.next_cell_position(notebook),
            content={
                "question": "Не удалось выполнить SQL ячейку.",
                "errors": validation.get("errors", []),
                "warnings": validation.get("warnings", []),
            },
        )
        db.add(error_cell)
        notebook.cells.append(error_cell)
        self.notebook_service.touch_notebook(notebook)
        db.commit()

        return PromptRunResponse(
            notebook_id=notebook.id,
            query_run_id=query_run.id,
            prompt_cell_id=sql_cell.id,
            generated_cell_ids=[error_cell.id],
            status=query_run.status,
        )

    def _build_explanation(self, intent: IntentPayload, semantic: Any) -> dict[str, Any]:
        return {
            "metric": intent.metric,
            "dimensions": intent.dimensions,
            "filters": [item.model_dump(mode="json") for item in intent.filters],
            "comparison": intent.comparison,
            "warnings": semantic.warnings,
            "source": "rules",
        }

    def _build_chart_spec(
        self,
        prompt: str,
        plan: LLMQueryPlan,
        execution: QueryExecutionResult,
    ) -> ChartSpec:
        numeric_columns = self._detect_numeric_columns(execution)
        dimension_columns = [column for column in execution.columns if column not in numeric_columns]

        x_field = plan.chart_x_field if plan.chart_x_field in execution.columns else None
        y_field = plan.chart_y_field if plan.chart_y_field in execution.columns else None

        if x_field is None and dimension_columns:
            x_field = dimension_columns[0]
        if y_field is None and numeric_columns:
            y_field = numeric_columns[0]

        chart_type = plan.chart_type or plan.intent.visualization_preference
        if chart_type not in {"line", "bar", "pie", "table"}:
            chart_type = self._infer_chart_type(x_field, y_field)

        if chart_type in {"line", "bar", "pie"} and (x_field is None or y_field is None):
            chart_type = "table"

        return ChartSpec(
            chart_type=chart_type,
            title=plan.chart_title or prompt.strip()[:80] or "Query Result",
            encoding=ChartEncoding(x_field=x_field, y_field=y_field),
            options={"rowCount": execution.row_count},
        )

    def _build_manual_chart_spec(self, execution: QueryExecutionResult) -> ChartSpec:
        numeric_columns = self._detect_numeric_columns(execution)
        dimension_columns = [column for column in execution.columns if column not in numeric_columns]
        x_field = dimension_columns[0] if dimension_columns else None
        y_field = numeric_columns[0] if numeric_columns else None
        chart_type = self._infer_chart_type(x_field, y_field)
        if chart_type in {"line", "bar", "pie"} and (x_field is None or y_field is None):
            chart_type = "table"

        return ChartSpec(
            chart_type=chart_type,
            title="Manual SQL Result",
            encoding=ChartEncoding(x_field=x_field, y_field=y_field),
            options={"rowCount": execution.row_count},
        )

    def _resolve_dialect(self, db: Session, notebook: NotebookModel) -> str:
        if notebook.database_id == settings.demo_database_id:
            return analytics_engine.dialect.name

        connection = (
            db.query(DatabaseConnectionModel)
            .filter(DatabaseConnectionModel.id == notebook.database_id)
            .first()
        )
        if connection is not None and connection.dialect:
            return connection.dialect
        return analytics_engine.dialect.name

    def _resolve_allowed_tables(self, db: Session, notebook: NotebookModel) -> list[str]:
        if notebook.database_id == settings.demo_database_id:
            return self.metadata_service.list_table_names()

        connection = (
            db.query(DatabaseConnectionModel)
            .filter(DatabaseConnectionModel.id == notebook.database_id)
            .first()
        )
        allowed_tables = connection.allowed_tables if connection is not None else None
        if isinstance(allowed_tables, list) and allowed_tables:
            return [str(table) for table in allowed_tables]

        metadata_tables = self.metadata_service.list_table_names()
        if metadata_tables:
            return metadata_tables
        return list(settings.allowed_tables)

    def _infer_chart_type(self, x_field: str | None, y_field: str | None) -> str:
        if x_field is None or y_field is None:
            return "table"
        if self._looks_temporal(x_field):
            return "line"
        return "bar"

    def _build_generic_insight(self, execution: QueryExecutionResult, chart_spec: ChartSpec) -> str:
        if not execution.rows:
            return "Запрос выполнен, но данных не найдено."

        metric_column = chart_spec.encoding.y_field
        dimension_column = chart_spec.encoding.x_field
        if metric_column is None:
            return f"Запрос вернул {execution.row_count} строк."

        if dimension_column:
            series = [
                (str(row.get(dimension_column)), self._to_number(row.get(metric_column)))
                for row in execution.rows
                if row.get(metric_column) is not None
            ]
            series = [(label, value) for label, value in series if value is not None]
            if not series:
                return f"Данные получены, но колонка {metric_column} не содержит числовых значений."
            if self._looks_temporal(dimension_column) and len(series) >= 2:
                first_label, first_value = series[0]
                last_label, last_value = series[-1]
                if first_value == 0:
                    return f"Последняя точка {last_label} имеет значение {self._fmt(last_value)}."
                delta = ((last_value - first_value) / first_value) * 100
                direction = "вырос" if delta >= 0 else "снизился"
                return (
                    f"Показатель {direction} на {self._fmt(abs(delta))}% "
                    f"между {first_label} и {last_label}."
                )
            leader_label, leader_value = max(series, key=lambda item: item[1])
            return f"Лидирует {leader_label}: {self._fmt(leader_value)}."

        first_value = self._to_number(execution.rows[0].get(metric_column))
        if first_value is None:
            return f"Запрос вернул {execution.row_count} строк."
        return f"По запросу получено значение {self._fmt(first_value)}."

    def _detect_numeric_columns(self, execution: QueryExecutionResult) -> list[str]:
        numeric_columns: list[str] = []
        sample_rows = execution.rows[:20]
        for column in execution.columns:
            sample_values = [row.get(column) for row in sample_rows if row.get(column) is not None]
            if sample_values and all(self._to_number(value) is not None for value in sample_values):
                numeric_columns.append(column)
        return numeric_columns

    def _looks_temporal(self, column_name: str) -> bool:
        lowered = column_name.lower()
        return any(token in lowered for token in ("date", "day", "week", "month", "year", "time"))

    def _to_number(self, value: object) -> float | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace(" ", "").replace(",", "."))
            except ValueError:
                return None
        return None

    def _fmt(self, value: float) -> str:
        if abs(value) >= 1000:
            return f"{value:,.2f}".replace(",", " ")
        return f"{value:.2f}"
