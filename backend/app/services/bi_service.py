from __future__ import annotations

import json
import math
import re
import time
from datetime import date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    DashboardModel,
    DashboardWidgetModel,
    DatasetModel,
    WidgetModel,
    WidgetRunModel,
    utcnow,
)
from app.schemas.bi import (
    BiChartEncoding,
    BiChartSpec,
    BiFieldRead,
    BiFilterCondition,
    ChartPreviewResponse,
    ChartRecommendationRead,
    ChartValidationResponse,
    DatasetRead,
)
from app.services.chat_execution_service import ChatExecutionService
from app.services.database_resolution import resolve_dialect, resolve_engine


class BiService:
    """Application BI layer over datasets, chart specs and dashboard widgets.

    The service intentionally reuses the existing DatasetModel and WidgetModel:
    a saved BI chart is a widget with a compiled SQL query and a stored ChartSpec.
    """

    NUMERIC_TYPE_HINTS = ("int", "numeric", "decimal", "float", "double", "real", "money", "number")
    DATE_TYPE_HINTS = ("date", "time", "timestamp", "datetime")
    MEASURE_NAME_HINTS = (
        "amount",
        "avg",
        "balance",
        "count",
        "cost",
        "gmv",
        "income",
        "margin",
        "metric",
        "orders",
        "price",
        "profit",
        "quantity",
        "revenue",
        "sales",
        "sum",
        "total",
        "value",
        "выруч",
        "доход",
        "прибыл",
        "сумм",
        "колич",
    )
    TEMPORAL_NAME_HINTS = ("date", "time", "day", "week", "month", "year", "created", "updated", "_at", "дата")
    CATEGORICAL_ID_HINTS = ("_id", "id", "uuid", "guid")

    def __init__(self) -> None:
        self.execution_service = ChatExecutionService()

    # ------------------------------------------------------------------
    # Dataset DTOs
    # ------------------------------------------------------------------

    def list_datasets(self, db: Session) -> list[DatasetRead]:
        datasets = (
            db.query(DatasetModel)
            .options(selectinload(DatasetModel.widgets))
            .order_by(DatasetModel.created_at.desc())
            .all()
        )
        return [self.dataset_to_read(item) for item in datasets]

    def get_dataset_or_raise(self, db: Session, dataset_id: str) -> DatasetModel:
        dataset = (
            db.query(DatasetModel)
            .options(selectinload(DatasetModel.widgets))
            .filter(DatasetModel.id == dataset_id)
            .first()
        )
        if dataset is None:
            raise ValueError("Dataset not found.")
        return dataset

    def dataset_to_read(self, dataset: DatasetModel) -> DatasetRead:
        preview_rows = list(dataset.preview_rows or [])
        columns = list(dataset.columns_schema or [])
        fields = self.infer_fields(columns, preview_rows)
        return DatasetRead.model_validate(
            {
                "id": dataset.id,
                "name": dataset.name,
                "database_connection_id": dataset.database_connection_id,
                "source_type": dataset.source_type,
                "source_query_execution_id": dataset.source_query_execution_id,
                "sql": dataset.sql,
                "columns_schema": columns,
                "fields": [field.model_dump(mode="json") for field in fields],
                "preview_rows": preview_rows,
                "row_count": dataset.row_count,
                "widgets_count": len([widget for widget in (dataset.widgets or []) if widget.deleted_at is None]),
                "created_by": dataset.created_by,
                "created_at": dataset.created_at,
                "refresh_policy": dataset.refresh_policy,
                "last_refresh_at": dataset.last_refresh_at,
            }
        )

    def infer_fields(self, columns: list[dict[str, Any]], rows: list[dict[str, Any]]) -> list[BiFieldRead]:
        result: list[BiFieldRead] = []
        for column in columns:
            name = str(column.get("name") or "").strip()
            if not name:
                continue
            source_type = str(column.get("type") or column.get("source_type") or "").strip()
            values = [row.get(name) for row in rows if row.get(name) is not None]
            data_type = self._infer_data_type(source_type, name, values)
            role = self._infer_semantic_role(name, data_type)
            default_aggregation = None
            if role == "measure":
                default_aggregation = "sum"
            distinct_values = {self._normalize_value(value) for value in values}
            distinct_values.discard(None)
            samples: list[Any] = []
            for value in values:
                normalized = self._normalize_value(value)
                if normalized is None or normalized in samples:
                    continue
                samples.append(normalized)
                if len(samples) >= 6:
                    break
            result.append(
                BiFieldRead(
                    name=name,
                    source_type=source_type,
                    data_type=data_type,
                    semantic_role=role,
                    default_aggregation=default_aggregation,
                    distinct_count=len(distinct_values),
                    sample_values=samples,
                )
            )
        return result

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def recommend_charts(self, dataset: DatasetModel) -> list[ChartRecommendationRead]:
        fields = self.infer_fields(list(dataset.columns_schema or []), list(dataset.preview_rows or []))
        measures = [field for field in fields if field.semantic_role == "measure"]
        times = [field for field in fields if field.semantic_role == "time"]
        dimensions = [field for field in fields if field.semantic_role == "dimension"]
        recommendations: list[ChartRecommendationRead] = []

        primary_measure = measures[0] if measures else None
        primary_time = times[0] if times else None
        primary_dimension = self._best_dimension(dimensions) if dimensions else None
        secondary_dimension = self._best_dimension([item for item in dimensions if item.name != (primary_dimension.name if primary_dimension else None)])

        if primary_measure is not None:
            recommendations.append(
                ChartRecommendationRead(
                    title=f"KPI: {primary_measure.name}",
                    score=0.84,
                    reason="Одна главная числовая метрика хорошо работает как KPI-карточка.",
                    chart_spec=BiChartSpec(
                        chart_type="metric_card",
                        title=f"{primary_measure.name}",
                        dataset_id=dataset.id,
                        encoding=BiChartEncoding(
                            y_field=primary_measure.name,
                            aggregation=primary_measure.default_aggregation or "sum",
                            value_format=self._guess_value_format(primary_measure.name),
                        ),
                        rule_id="bi_kpi_primary_measure",
                        confidence=0.84,
                    ),
                )
            )

        if primary_time is not None and primary_measure is not None:
            recommendations.append(
                ChartRecommendationRead(
                    title=f"{primary_measure.name} по {primary_time.name}",
                    score=0.93,
                    reason="Временная колонка и числовая метрика дают понятный тренд.",
                    chart_spec=BiChartSpec(
                        chart_type="line",
                        title=f"{primary_measure.name} по {primary_time.name}",
                        dataset_id=dataset.id,
                        encoding=BiChartEncoding(
                            x_field=primary_time.name,
                            y_field=primary_measure.name,
                            aggregation=primary_measure.default_aggregation or "sum",
                            sort="x_asc",
                            category_limit=300,
                            value_format=self._guess_value_format(primary_measure.name),
                        ),
                        rule_id="bi_time_series",
                        confidence=0.93,
                    ),
                )
            )

        if primary_dimension is not None and primary_measure is not None:
            chart_type = "pie" if (primary_dimension.distinct_count or 999) <= 6 else "bar"
            recommendations.append(
                ChartRecommendationRead(
                    title=f"{primary_measure.name} по {primary_dimension.name}",
                    score=0.9,
                    reason="Категория и числовая метрика подходят для сравнения сегментов.",
                    chart_spec=BiChartSpec(
                        chart_type=chart_type,
                        title=f"{primary_measure.name} по {primary_dimension.name}",
                        dataset_id=dataset.id,
                        encoding=BiChartEncoding(
                            x_field=primary_dimension.name,
                            y_field=primary_measure.name,
                            aggregation=primary_measure.default_aggregation or "sum",
                            sort="y_desc",
                            category_limit=10,
                            value_format=self._guess_value_format(primary_measure.name),
                        ),
                        rule_id="bi_category_ranking",
                        confidence=0.9,
                    ),
                )
            )

        if primary_time is not None and primary_measure is not None and secondary_dimension is not None:
            recommendations.append(
                ChartRecommendationRead(
                    title=f"{primary_measure.name} по {primary_time.name} и {secondary_dimension.name}",
                    score=0.86,
                    reason="Временной тренд с разбивкой помогает сравнить сегменты во времени.",
                    chart_spec=BiChartSpec(
                        chart_type="line",
                        title=f"{primary_measure.name}: тренд по {secondary_dimension.name}",
                        dataset_id=dataset.id,
                        encoding=BiChartEncoding(
                            x_field=primary_time.name,
                            y_field=primary_measure.name,
                            series_field=secondary_dimension.name,
                            aggregation=primary_measure.default_aggregation or "sum",
                            sort="x_asc",
                            category_limit=300,
                            series_limit=8,
                            value_format=self._guess_value_format(primary_measure.name),
                        ),
                        rule_id="bi_time_series_breakdown",
                        confidence=0.86,
                    ),
                )
            )
        elif primary_dimension is not None and secondary_dimension is not None and primary_measure is not None:
            recommendations.append(
                ChartRecommendationRead(
                    title=f"{primary_measure.name}: {primary_dimension.name} × {secondary_dimension.name}",
                    score=0.82,
                    reason="Две категориальные колонки и метрика подходят для stacked bar.",
                    chart_spec=BiChartSpec(
                        chart_type="bar",
                        title=f"{primary_measure.name}: {primary_dimension.name} × {secondary_dimension.name}",
                        dataset_id=dataset.id,
                        encoding=BiChartEncoding(
                            x_field=primary_dimension.name,
                            y_field=primary_measure.name,
                            series_field=secondary_dimension.name,
                            aggregation=primary_measure.default_aggregation or "sum",
                            sort="y_desc",
                            category_limit=12,
                            series_limit=8,
                            value_format=self._guess_value_format(primary_measure.name),
                        ),
                        variant="stacked",
                        rule_id="bi_stacked_category_breakdown",
                        confidence=0.82,
                    ),
                )
            )

        recommendations.append(
            ChartRecommendationRead(
                title="Табличный preview",
                score=0.65,
                reason="Таблица нужна для проверки исходных строк и drill-through.",
                chart_spec=BiChartSpec(
                    chart_type="table",
                    title=f"Таблица: {dataset.name}",
                    dataset_id=dataset.id,
                    encoding=BiChartEncoding(category_limit=100, aggregation="none"),
                    rule_id="bi_table_fallback",
                    confidence=0.65,
                ),
            )
        )

        # Keep useful, unique specs first.
        seen: set[str] = set()
        unique: list[ChartRecommendationRead] = []
        for recommendation in sorted(recommendations, key=lambda item: item.score, reverse=True):
            key = json.dumps(recommendation.chart_spec.model_dump(mode="json", exclude={"title", "reason", "explanation"}), sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            unique.append(recommendation)
        return unique[:6]

    # ------------------------------------------------------------------
    # Chart validation / SQL compilation / execution
    # ------------------------------------------------------------------

    def validate_chart_spec(
        self,
        dataset: DatasetModel,
        chart_spec: BiChartSpec,
        extra_filters: list[BiFilterCondition] | None = None,
    ) -> ChartValidationResponse:
        errors: list[str] = []
        warnings: list[str] = []
        normalized = chart_spec.model_copy(deep=True)
        normalized.dataset_id = dataset.id
        normalized.filters = [*normalized.filters, *(extra_filters or [])]
        fields = {str(column.get("name")) for column in list(dataset.columns_schema or []) if column.get("name")}

        def check_field(field: str | None, role: str) -> None:
            if field and field not in fields:
                errors.append(f"Поле {role}='{field}' не найдено в dataset.")

        check_field(normalized.encoding.x_field, "x")
        check_field(normalized.encoding.y_field, "y")
        check_field(normalized.encoding.series_field, "series")
        for item in normalized.filters:
            check_field(item.field, "filter")

        if normalized.chart_type in {"line", "bar", "area", "pie"} and not normalized.encoding.x_field:
            errors.append("Для графика нужен X axis.")
        if normalized.chart_type in {"line", "bar", "area", "pie", "metric_card"}:
            if normalized.encoding.aggregation not in {"count"} and not normalized.encoding.y_field:
                errors.append("Для графика нужна Y metric или aggregation=count.")

        if normalized.chart_type == "pie" and normalized.encoding.series_field:
            warnings.append("Pie chart не использует series; разбивка будет проигнорирована.")
            normalized.encoding.series_field = None

        if normalized.chart_type == "metric_card":
            normalized.encoding.x_field = None
            normalized.encoding.series_field = None
            normalized.encoding.sort = None
            normalized.encoding.category_limit = 1

        if normalized.chart_type == "table":
            normalized.encoding.aggregation = "none"

        sql = None
        if not errors:
            try:
                sql = self.compile_chart_sql(dataset, normalized)
            except Exception as exc:  # noqa: BLE001
                errors.append(str(exc))

        return ChartValidationResponse(
            valid=not errors,
            chart_spec=None if errors else normalized,
            errors=errors,
            warnings=warnings,
            sql=sql,
        )

    def compile_chart_sql(self, dataset: DatasetModel, chart_spec: BiChartSpec) -> str:
        dialect = "postgresql"
        # compile SQL can be called without a DB session from validation tests; use PostgreSQL quoting as default.
        base_sql = self._strip_sql(dataset.sql)
        if not base_sql:
            raise ValueError("Dataset SQL is empty.")
        fields = {str(column.get("name")) for column in list(dataset.columns_schema or []) if column.get("name")}
        spec = chart_spec.model_copy(deep=True)
        alias = "__bi_dataset"
        where_sql = self._compile_where(spec.filters, fields, dialect, alias)
        limit = max(1, min(int(spec.encoding.category_limit or 100), 500))

        if spec.chart_type == "table":
            return f"SELECT * FROM ({base_sql}) AS {alias}{where_sql} LIMIT {limit}"

        y_alias = spec.encoding.y_field or "value"
        y_expr = self._compile_metric_expr(spec.encoding.y_field, spec.encoding.aggregation, dialect, alias)

        if spec.chart_type == "metric_card":
            return f"SELECT {y_expr} AS {self._quote_identifier(y_alias, dialect)} FROM ({base_sql}) AS {alias}{where_sql}"

        if not spec.encoding.x_field:
            raise ValueError("X field is required for this chart type.")

        x_field = spec.encoding.x_field
        x_expr = self._column_ref(x_field, dialect, alias)
        select_parts = [f"{x_expr} AS {self._quote_identifier(x_field, dialect)}"]
        group_parts = [x_expr]

        if spec.chart_type != "pie" and spec.encoding.series_field:
            series_field = spec.encoding.series_field
            series_expr = self._column_ref(series_field, dialect, alias)
            select_parts.append(f"{series_expr} AS {self._quote_identifier(series_field, dialect)}")
            group_parts.append(series_expr)

        select_parts.append(f"{y_expr} AS {self._quote_identifier(y_alias, dialect)}")
        order_sql = self._compile_order_by(spec, y_alias, dialect)
        return (
            f"SELECT {', '.join(select_parts)} "
            f"FROM ({base_sql}) AS {alias}"
            f"{where_sql} "
            f"GROUP BY {', '.join(group_parts)}"
            f"{order_sql} "
            f"LIMIT {limit}"
        )

    def compile_chart_sql_for_execution(self, db: Session, dataset: DatasetModel, chart_spec: BiChartSpec) -> str:
        # Uses the actual dialect for identifier quoting. Validation still controls the input fields.
        dialect = resolve_dialect(db, dataset.database_connection_id)
        base_sql = self._strip_sql(dataset.sql)
        fields = {str(column.get("name")) for column in list(dataset.columns_schema or []) if column.get("name")}
        spec = chart_spec.model_copy(deep=True)
        alias = "__bi_dataset"
        where_sql = self._compile_where(spec.filters, fields, dialect, alias)
        limit = max(1, min(int(spec.encoding.category_limit or 100), 500))

        if spec.chart_type == "table":
            return f"SELECT * FROM ({base_sql}) AS {alias}{where_sql} LIMIT {limit}"

        y_alias = spec.encoding.y_field or "value"
        y_expr = self._compile_metric_expr(spec.encoding.y_field, spec.encoding.aggregation, dialect, alias)

        if spec.chart_type == "metric_card":
            return f"SELECT {y_expr} AS {self._quote_identifier(y_alias, dialect)} FROM ({base_sql}) AS {alias}{where_sql}"

        x_field = spec.encoding.x_field
        if not x_field:
            raise ValueError("X field is required for this chart type.")
        x_expr = self._column_ref(x_field, dialect, alias)
        select_parts = [f"{x_expr} AS {self._quote_identifier(x_field, dialect)}"]
        group_parts = [x_expr]

        if spec.chart_type != "pie" and spec.encoding.series_field:
            series_field = spec.encoding.series_field
            series_expr = self._column_ref(series_field, dialect, alias)
            select_parts.append(f"{series_expr} AS {self._quote_identifier(series_field, dialect)}")
            group_parts.append(series_expr)

        select_parts.append(f"{y_expr} AS {self._quote_identifier(y_alias, dialect)}")
        order_sql = self._compile_order_by(spec, y_alias, dialect)
        return (
            f"SELECT {', '.join(select_parts)} "
            f"FROM ({base_sql}) AS {alias}"
            f"{where_sql} "
            f"GROUP BY {', '.join(group_parts)}"
            f"{order_sql} "
            f"LIMIT {limit}"
        )

    def preview_chart(
        self,
        db: Session,
        dataset: DatasetModel,
        chart_spec: BiChartSpec,
        extra_filters: list[BiFilterCondition] | None = None,
    ) -> ChartPreviewResponse:
        validation = self.validate_chart_spec(dataset, chart_spec, extra_filters)
        if not validation.valid or validation.chart_spec is None:
            raise ValueError("; ".join(validation.errors) or "Invalid chart spec.")
        spec = validation.chart_spec
        sql = self.compile_chart_sql_for_execution(db, dataset, spec)
        rows, columns, row_count, truncated, elapsed_ms = self._execute_sql(db, dataset.database_connection_id, sql)
        return ChartPreviewResponse(
            chart_spec=spec,
            sql=sql,
            columns=columns,
            rows=rows,
            row_count=row_count,
            rows_preview_truncated=truncated,
            execution_time_ms=elapsed_ms,
            warnings=validation.warnings,
        )

    def refresh_dataset(self, db: Session, dataset: DatasetModel) -> DatasetModel:
        rows, columns, row_count, _truncated, _elapsed_ms = self._execute_sql(db, dataset.database_connection_id, dataset.sql)
        dataset.columns_schema = columns
        dataset.preview_rows = rows
        dataset.row_count = row_count
        dataset.last_refresh_at = utcnow()
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return dataset

    def save_chart_widget(
        self,
        db: Session,
        dataset: DatasetModel,
        chart_spec: BiChartSpec,
        *,
        title: str | None = None,
        description: str | None = None,
        run_immediately: bool = True,
        commit: bool = True,
    ) -> tuple[WidgetModel, ChartPreviewResponse | None]:
        preview = self.preview_chart(db, dataset, chart_spec) if run_immediately else None
        spec = (preview.chart_spec if preview else chart_spec).model_copy(deep=True)
        spec.dataset_id = dataset.id
        compiled_sql = preview.sql if preview else self.compile_chart_sql_for_execution(db, dataset, spec)
        widget = WidgetModel(
            title=(title or spec.title or "BI chart")[:255],
            description=description or spec.reason or spec.explanation,
            source_type="sql",
            dataset_id=dataset.id,
            sql_text=compiled_sql,
            visualization_type=self._visualization_type_for_spec(spec),
            visualization_config=self._visualization_config_for_spec(spec),
            chart_spec_json=spec.model_dump(mode="json"),
            result_schema={"columns": preview.columns} if preview else None,
            refresh_policy="on_view",
            database_connection_id=dataset.database_connection_id,
        )
        db.add(widget)
        db.flush()

        if preview is not None:
            run = WidgetRunModel(
                widget_id=widget.id,
                status="completed",
                columns_json=preview.columns,
                rows_preview_json=preview.rows,
                rows_preview_truncated=preview.rows_preview_truncated,
                row_count=preview.row_count,
                execution_time_ms=preview.execution_time_ms,
                error_text=None,
                finished_at=utcnow(),
            )
            db.add(run)
            db.flush()

        if commit:
            db.commit()
            db.refresh(widget)
        return widget, preview

    def create_dashboard_from_recommendations(
        self,
        db: Session,
        dataset: DatasetModel,
        *,
        title: str | None = None,
        max_widgets: int = 4,
    ) -> tuple[DashboardModel, list[WidgetModel], list[ChartRecommendationRead]]:
        recommendations = [item for item in self.recommend_charts(dataset) if item.chart_spec.chart_type != "table"][:max_widgets]
        if not recommendations:
            recommendations = self.recommend_charts(dataset)[:1]

        dashboard = DashboardModel(
            title=(title or f"BI dashboard: {dataset.name}")[:255],
            description=f"Auto-generated dashboard from dataset {dataset.name}",
            is_public=False,
            is_hidden=False,
        )
        db.add(dashboard)
        db.flush()

        widgets: list[WidgetModel] = []
        for index, recommendation in enumerate(recommendations):
            widget, _preview = self.save_chart_widget(
                db,
                dataset,
                recommendation.chart_spec,
                title=recommendation.title,
                description=recommendation.reason,
                run_immediately=True,
                commit=False,
            )
            widgets.append(widget)
            layout = {
                "x": (index % 2) * 6,
                "y": (index // 2) * 4,
                "w": 6,
                "h": 4,
            }
            db.add(
                DashboardWidgetModel(
                    dashboard_id=dashboard.id,
                    widget_id=widget.id,
                    layout=layout,
                    title_override=None,
                    display_options={"source": "bi_quick_dashboard", "dataset_id": dataset.id},
                )
            )
        db.commit()
        db.refresh(dashboard)
        return dashboard, widgets, recommendations

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _execute_sql(
        self,
        db: Session,
        database_connection_id: str,
        sql: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, bool, int]:
        dialect = resolve_dialect(db, database_connection_id)
        engine = resolve_engine(db, database_connection_id)
        started = time.perf_counter()
        with engine.begin() as connection:
            self.execution_service._apply_read_only_guards(connection, dialect)
            dataframe: pd.DataFrame = pd.read_sql_query(sa_text(sql), connection)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        columns = self.execution_service._serialize_columns(dataframe)
        rows_full = json.loads(dataframe.to_json(orient="records", date_format="iso"))
        rows_preview, truncated = self.execution_service._serialize_preview(rows_full)
        return rows_preview, columns, int(len(dataframe.index)), truncated, elapsed_ms

    def _strip_sql(self, sql: str) -> str:
        text = str(sql or "").strip()
        while text.endswith(";"):
            text = text[:-1].strip()
        return text

    def _compile_metric_expr(self, field: str | None, aggregation: str | None, dialect: str, alias: str) -> str:
        aggregation = (aggregation or "sum").lower()
        if aggregation == "count":
            if field:
                return f"COUNT({self._column_ref(field, dialect, alias)})"
            return "COUNT(*)"
        if not field:
            raise ValueError("Metric field is required for this aggregation.")
        column = self._column_ref(field, dialect, alias)
        if aggregation == "count_distinct":
            return f"COUNT(DISTINCT {column})"
        if aggregation == "avg":
            return f"AVG({column})"
        if aggregation == "min":
            return f"MIN({column})"
        if aggregation == "max":
            return f"MAX({column})"
        if aggregation == "none":
            return column
        return f"SUM({column})"

    def _compile_where(self, filters: list[BiFilterCondition], fields: set[str], dialect: str, alias: str) -> str:
        parts: list[str] = []
        for item in filters:
            if item.field not in fields:
                raise ValueError(f"Filter field '{item.field}' not found in dataset.")
            parts.append(self._compile_filter(item, dialect, alias))
        if not parts:
            return ""
        return " WHERE " + " AND ".join(f"({part})" for part in parts)

    def _compile_filter(self, item: BiFilterCondition, dialect: str, alias: str) -> str:
        column = self._column_ref(item.field, dialect, alias)
        operator = item.operator
        if operator == "is_null":
            return f"{column} IS NULL"
        if operator == "is_not_null":
            return f"{column} IS NOT NULL"
        if operator in {"=", "!=", ">", ">=", "<", "<="}:
            sql_operator = "<>" if operator == "!=" else operator
            return f"{column} {sql_operator} {self._literal(item.value)}"
        if operator in {"in", "not_in"}:
            values = item.value if isinstance(item.value, list) else [item.value]
            if not values:
                return "1=0" if operator == "in" else "1=1"
            in_sql = ", ".join(self._literal(value) for value in values)
            negation = "NOT " if operator == "not_in" else ""
            return f"{column} {negation}IN ({in_sql})"
        if operator == "between":
            values = item.value if isinstance(item.value, list) else []
            if len(values) != 2:
                raise ValueError(f"Filter '{item.field}' expects two values for between.")
            return f"{column} BETWEEN {self._literal(values[0])} AND {self._literal(values[1])}"
        if operator == "contains":
            value = str(item.value or "").replace("%", "\\%").replace("_", "\\_")
            literal = self._literal(f"%{value}%")
            if dialect.startswith("postgres"):
                return f"CAST({column} AS TEXT) ILIKE {literal}"
            return f"LOWER(CAST({column} AS TEXT)) LIKE LOWER({literal})"
        raise ValueError(f"Unsupported filter operator: {operator}")

    def _compile_order_by(self, spec: BiChartSpec, y_alias: str, dialect: str) -> str:
        sort = spec.encoding.sort
        if sort == "none":
            return ""
        if sort is None:
            sort = "x_asc" if spec.chart_type in {"line", "area"} else "y_desc"
        x_field = spec.encoding.x_field
        if sort == "x_asc" and x_field:
            return f" ORDER BY {self._quote_identifier(x_field, dialect)} ASC"
        if sort == "x_desc" and x_field:
            return f" ORDER BY {self._quote_identifier(x_field, dialect)} DESC"
        if sort == "y_asc":
            return f" ORDER BY {self._quote_identifier(y_alias, dialect)} ASC"
        if sort == "y_desc":
            return f" ORDER BY {self._quote_identifier(y_alias, dialect)} DESC"
        return ""

    def _column_ref(self, field: str, dialect: str, alias: str) -> str:
        return f"{alias}.{self._quote_identifier(field, dialect)}"

    def _quote_identifier(self, identifier: str, dialect: str) -> str:
        escaped = str(identifier).replace('"', '""').replace("`", "``")
        if dialect.startswith("mysql") or dialect.startswith("mariadb"):
            return f"`{escaped}`"
        return f'"{escaped}"'

    def _literal(self, value: Any) -> str:
        if value is None:
            return "NULL"
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if isinstance(value, float) and not math.isfinite(value):
                return "NULL"
            return str(value)
        if isinstance(value, (datetime, date)):
            value = value.isoformat()
        text = str(value).replace("'", "''")
        return f"'{text}'"

    def _visualization_type_for_spec(self, spec: BiChartSpec) -> str:
        if spec.chart_type == "metric_card":
            return "metric"
        if spec.chart_type == "area":
            return "area"
        return spec.chart_type

    def _visualization_config_for_spec(self, spec: BiChartSpec) -> dict[str, Any]:
        return {
            "chart_spec": spec.model_dump(mode="json"),
            "chart_type": spec.chart_type,
            "variant": spec.variant,
            "x": spec.encoding.x_field,
            "y": spec.encoding.y_field,
            "series": spec.encoding.series_field,
            "aggregation": spec.encoding.aggregation,
            "sort": spec.encoding.sort,
            "filters": [item.model_dump(mode="json") for item in spec.filters],
        }

    def _infer_data_type(self, source_type: str, name: str, values: list[Any]) -> str:
        lowered_type = source_type.lower()
        if any(hint in lowered_type for hint in self.DATE_TYPE_HINTS) or self._looks_temporal_name(name) or self._looks_temporal_values(values):
            return "datetime" if "time" in lowered_type or "timestamp" in lowered_type else "date"
        if "bool" in lowered_type:
            return "boolean"
        if any(hint in lowered_type for hint in self.NUMERIC_TYPE_HINTS) or self._looks_numeric_values(values):
            return "number"
        if "object" in lowered_type or "str" in lowered_type or "char" in lowered_type or "text" in lowered_type:
            return "string"
        return "unknown"

    def _infer_semantic_role(self, name: str, data_type: str) -> str:
        lowered = name.lower()
        if data_type in {"date", "datetime"}:
            return "time"
        if data_type == "number":
            if lowered in self.CATEGORICAL_ID_HINTS or lowered.endswith("_id") or lowered.endswith("id"):
                return "dimension"
            if any(hint in lowered for hint in self.MEASURE_NAME_HINTS):
                return "measure"
            return "measure"
        if data_type in {"string", "boolean"}:
            return "dimension"
        return "unknown"

    def _best_dimension(self, dimensions: list[BiFieldRead]) -> BiFieldRead | None:
        if not dimensions:
            return None
        return sorted(
            dimensions,
            key=lambda field: (
                999999 if field.distinct_count is None else field.distinct_count,
                len(field.name),
            ),
        )[0]

    def _guess_value_format(self, field_name: str) -> str | None:
        lowered = field_name.lower()
        if any(token in lowered for token in ("revenue", "amount", "price", "cost", "profit", "gmv", "выруч", "сумм", "доход")):
            return "currency"
        if any(token in lowered for token in ("percent", "pct", "ratio", "share", "conversion", "rate", "доля", "процент")):
            return "percent"
        if any(token in lowered for token in ("count", "orders", "qty", "quantity", "колич")):
            return "integer"
        return "compact"

    def _looks_temporal_name(self, name: str) -> bool:
        lowered = name.lower()
        return any(hint in lowered for hint in self.TEMPORAL_NAME_HINTS)

    def _looks_numeric_values(self, values: list[Any]) -> bool:
        if not values:
            return False
        numeric = 0
        for value in values:
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                numeric += 1
                continue
            try:
                float(str(value).replace(",", "."))
                numeric += 1
            except Exception:  # noqa: BLE001
                continue
        return numeric >= max(1, math.ceil(len(values) * 0.7))

    def _looks_temporal_values(self, values: list[Any]) -> bool:
        if not values:
            return False
        temporal = 0
        for value in values:
            if isinstance(value, (datetime, date)):
                temporal += 1
                continue
            text = str(value).strip()
            if not text:
                continue
            if re.match(r"^\d{4}-\d{2}-\d{2}", text):
                temporal += 1
                continue
            try:
                datetime.fromisoformat(text.replace("Z", "+00:00"))
                temporal += 1
            except Exception:  # noqa: BLE001
                continue
        return temporal >= max(1, math.ceil(len(values) * 0.6))

    def _normalize_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, float):
            if not math.isfinite(value):
                return None
            return round(value, 6)
        if isinstance(value, (int, bool)):
            return value
        text = str(value).strip()
        return text or None
