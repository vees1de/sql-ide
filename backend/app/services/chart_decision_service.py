from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.query import (
    ChartEncoding,
    ChartSpec,
    QueryExecutionResult,
    QuerySemantics,
    SemanticComparisonPayload,
    SemanticFlagsPayload,
    SemanticTimePayload,
)


class ColumnInfo(BaseModel):
    name: str
    kind: Literal["temporal", "numeric", "categorical", "unknown"] = "unknown"
    distinct_count: int = 0
    non_null_count: int = 0

    @property
    def is_temporal(self) -> bool:
        return self.kind == "temporal"

    @property
    def is_numeric(self) -> bool:
        return self.kind == "numeric"

    @property
    def is_categorical(self) -> bool:
        return self.kind == "categorical"


class ResultShape(BaseModel):
    row_count: int = 0
    columns: list[ColumnInfo] = Field(default_factory=list)
    temporal_columns: list[ColumnInfo] = Field(default_factory=list)
    numeric_columns: list[ColumnInfo] = Field(default_factory=list)
    categorical_columns: list[ColumnInfo] = Field(default_factory=list)
    series_column: ColumnInfo | None = None

    def column(self, name: str | None) -> ColumnInfo | None:
        if not name:
            return None
        for column in self.columns:
            if column.name == name:
                return column
        return None

    def cardinality(self, name: str | None) -> int:
        column = self.column(name)
        return column.distinct_count if column is not None else 0

    def x_candidates(self) -> list[ColumnInfo]:
        if self.temporal_columns:
            return self.temporal_columns
        return self.categorical_columns

    def y_candidate(self) -> ColumnInfo | None:
        return self.numeric_columns[0] if self.numeric_columns else None


class ChartDecision(BaseModel):
    chart_type: Literal["line", "bar", "pie", "metric_card", "table"]
    variant: str
    encoding: ChartEncoding = Field(default_factory=ChartEncoding)
    explanation: str
    rule_id: str
    confidence: float


class ResultShapeAnalyzer:
    CATEGORICAL_NAME_HINTS = (
        "_id",
        "_bucket",
        "_bin",
        "_group",
        "_rank",
        "_index",
    )
    TEMPORAL_NAME_HINTS = (
        "_date",
        "date",
        "_at",
        "time",
        "month",
        "day",
        "week",
        "year",
        "created",
        "updated",
    )
    NUMERIC_TYPE_HINTS = (
        "int",
        "numeric",
        "decimal",
        "float",
        "double",
        "real",
        "money",
        "number",
    )

    def analyze(self, execution: QueryExecutionResult) -> ResultShape:
        sample_rows = execution.rows[: min(len(execution.rows), 200)]
        columns = [self._analyse_column(name, sample_rows) for name in execution.columns]
        temporal_columns = [column for column in columns if column.is_temporal]
        numeric_columns = [column for column in columns if column.is_numeric]
        categorical_columns = [column for column in columns if column.is_categorical]
        series_column = self._detect_series_column(columns, temporal_columns, categorical_columns)
        return ResultShape(
            row_count=execution.row_count,
            columns=columns,
            temporal_columns=temporal_columns,
            numeric_columns=numeric_columns,
            categorical_columns=categorical_columns,
            series_column=series_column,
        )

    def _analyse_column(self, name: str, sample_rows: list[dict[str, Any]]) -> ColumnInfo:
        values = [row.get(name) for row in sample_rows if row.get(name) is not None]
        distinct_values = {self._normalize_value(value) for value in values}
        distinct_values.discard(None)
        kind = self._classify_kind(name, values)
        return ColumnInfo(
            name=name,
            kind=kind,
            distinct_count=len(distinct_values),
            non_null_count=len(values),
        )

    def _classify_kind(self, name: str, values: list[Any]) -> Literal["temporal", "numeric", "categorical", "unknown"]:
        lowered = name.lower()
        if self._looks_temporal_name(lowered) or self._looks_temporal_values(values):
            return "temporal"
        if self._looks_numeric_name(lowered) or self._looks_numeric_values(values):
            if not self._looks_categorical_name(lowered):
                return "numeric"
        if values:
            return "categorical"
        return "unknown"

    def _looks_categorical_name(self, lowered_name: str) -> bool:
        return any(hint in lowered_name for hint in self.CATEGORICAL_NAME_HINTS)

    def _looks_numeric_name(self, lowered_name: str) -> bool:
        return any(hint in lowered_name for hint in self.NUMERIC_TYPE_HINTS)

    def _looks_temporal_name(self, lowered_name: str) -> bool:
        return any(hint in lowered_name for hint in self.TEMPORAL_NAME_HINTS)

    def _looks_numeric_values(self, values: list[Any]) -> bool:
        if not values:
            return False
        numeric = 0
        for value in values:
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                numeric += 1
                continue
            try:
                float(str(value).replace(",", "."))
            except Exception:
                continue
            numeric += 1
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
            except Exception:
                continue
        return temporal >= max(1, math.ceil(len(values) * 0.6))

    def _detect_series_column(
        self,
        columns: list[ColumnInfo],
        temporal_columns: list[ColumnInfo],
        categorical_columns: list[ColumnInfo],
    ) -> ColumnInfo | None:
        preferred = next(
            (
                column
                for column in columns
                if column.name == "comparison_series" or column.name.endswith("_series") or column.name == "series"
            ),
            None,
        )
        if preferred is not None:
            return preferred

        def _looks_like_entity_id(column: ColumnInfo) -> bool:
            lowered = column.name.lower()
            return lowered.endswith("_id") or lowered == "id"

        candidates = [
            column for column in categorical_columns
            if 2 <= column.distinct_count <= 12 and not _looks_like_entity_id(column)
        ]
        if temporal_columns and candidates:
            return candidates[0]
        if len(candidates) >= 2:
            return min(candidates, key=lambda column: column.distinct_count)
        if candidates:
            return candidates[0]
        return None

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, float):
            return round(value, 6)
        if isinstance(value, int):
            return value
        text = str(value).strip()
        return text or None


class ChartDecisionService:
    def __init__(self) -> None:
        self.analyzer = ResultShapeAnalyzer()

    def decide(
        self,
        semantics: QuerySemantics | None,
        execution: QueryExecutionResult,
    ) -> ChartDecision:
        shape = self.analyzer.analyze(execution)
        resolved_semantics = semantics or self._semantics_from_shape(shape)
        return self._decide(resolved_semantics, shape)

    def decide_for_semantics(self, semantics: QuerySemantics | None, shape: ResultShape) -> ChartDecision:
        resolved_semantics = semantics or self._semantics_from_shape(shape)
        return self._decide(resolved_semantics, shape)

    def _decide(self, semantics: QuerySemantics, shape: ResultShape) -> ChartDecision:
        semantics = self._reconcile_semantics_with_shape(semantics, shape)
        if shape.row_count == 0:
            return self._decision(
                chart_type="table",
                variant="empty_state",
                explanation="Нет данных для визуализации.",
                rule_id="R1",
                confidence=1.0,
            )

        explicit_request = bool(semantics.flags.explicit_chart_request and semantics.visualization_hint)
        if explicit_request:
            hinted = semantics.visualization_hint or "table"
            if self._is_shape_compatible(hinted, semantics, shape):
                return self._decision(
                    chart_type=self._normalize_chart_type(hinted),
                    variant="user_requested",
                    explanation=f"Вы явно запросили визуализацию типа «{hinted}».",
                    rule_id="R2",
                    confidence=0.95,
                    shape=shape,
                    semantics=semantics,
                )

        if semantics.flags.is_time_series and semantics.flags.is_comparison:
            series_column = self._series_column_for_comparison(semantics, shape)
            return self._decision(
                chart_type="line",
                variant="multi_series",
                explanation="Запрос распознан как сравнение динамики во времени, поэтому выбран линейный график с несколькими сериями.",
                rule_id="R3",
                confidence=0.9,
                shape=shape,
                semantics=semantics,
                series_column=series_column,
            )

        if semantics.flags.is_time_series:
            return self._decision(
                chart_type="line",
                variant="single_series",
                explanation="В запросе есть временная ось, поэтому выбран линейный график.",
                rule_id="R4",
                confidence=0.88,
                shape=shape,
                semantics=semantics,
            )

        if semantics.flags.is_comparison:
            return self._decision(
                chart_type="bar",
                variant="grouped",
                explanation="Запрос сравнивает категории без временной оси, поэтому выбран grouped bar chart.",
                rule_id="R5",
                confidence=0.86,
                shape=shape,
                semantics=semantics,
            )

        if semantics.flags.is_ranking or semantics.flags.top_n is not None:
            return self._decision(
                chart_type="bar",
                variant="horizontal_sorted",
                explanation="Запрос описывает ranking или top-N, поэтому выбран bar chart.",
                rule_id="R6",
                confidence=0.84,
                shape=shape,
                semantics=semantics,
            )

        if semantics.intent == "share" and self._x_cardinality(shape, semantics) <= 6:
            return self._decision(
                chart_type="pie",
                variant="single",
                explanation="Небольшая кардинальность и запрос на доли подходят для pie chart.",
                rule_id="R7",
                confidence=0.8,
                shape=shape,
                semantics=semantics,
            )

        if semantics.intent == "composition" and semantics.flags.is_time_series:
            return self._decision(
                chart_type="bar",
                variant="stacked",
                explanation="Запрос описывает состав во времени, поэтому выбран stacked bar chart.",
                rule_id="R8",
                confidence=0.8,
                shape=shape,
                semantics=semantics,
            )

        if not shape.categorical_columns and len(shape.numeric_columns) == 1 and shape.row_count == 1:
            numeric_column = shape.numeric_columns[0]
            return self._decision(
                chart_type="metric_card",
                variant="single_kpi",
                explanation="В результате один скаляр без категорий, поэтому выбран KPI card.",
                rule_id="R9",
                confidence=0.95,
                encoding=ChartEncoding(y_field=numeric_column.name),
            )

        candidate_chart_type = self._candidate_chart_type(shape)
        if candidate_chart_type in {"bar", "pie"} and self._x_cardinality(shape, semantics) > 50:
            return self._decision(
                chart_type="table",
                variant="high_cardinality_fallback",
                explanation="Слишком много категорий для читаемого графика, поэтому показана таблица.",
                rule_id="R10",
                confidence=0.7,
                shape=shape,
                semantics=semantics,
            )

        return self._decision(
            chart_type="table",
            variant="default",
            explanation="Набор данных лучше читается в табличном виде.",
            rule_id="R11",
            confidence=0.5,
            shape=shape,
            semantics=semantics,
        )

    def _decision(
        self,
        *,
        chart_type: Literal["line", "bar", "pie", "metric_card", "table"],
        variant: str,
        explanation: str,
        rule_id: str,
        confidence: float,
        shape: ResultShape | None = None,
        semantics: QuerySemantics | None = None,
        encoding: ChartEncoding | None = None,
        series_column: ColumnInfo | None = None,
    ) -> ChartDecision:
        resolved_shape = shape or ResultShape()
        resolved_semantics = semantics or QuerySemantics()
        resolved_encoding = encoding or self._build_encoding(
            chart_type,
            variant,
            resolved_shape,
            resolved_semantics,
            series_column,
        )
        if series_column is not None and resolved_encoding.series_field is None:
            resolved_encoding.series_field = series_column.name
        return ChartDecision(
            chart_type=chart_type,
            variant=variant,
            encoding=resolved_encoding,
            explanation=explanation,
            rule_id=rule_id,
            confidence=confidence,
        )

    def _build_encoding(
        self,
        chart_type: str,
        variant: str,
        shape: ResultShape,
        semantics: QuerySemantics,
        series_column: ColumnInfo | None = None,
    ) -> ChartEncoding:
        if chart_type == "metric_card":
            metric = shape.y_candidate()
            return ChartEncoding(y_field=metric.name if metric else None)

        x_field = self._resolve_x_field(shape, semantics)
        y_field = self._resolve_y_field(shape, semantics)
        resolved_series = series_column or shape.series_column
        if chart_type in {"line", "bar"} and variant in {"multi_series", "grouped", "stacked"} and resolved_series is not None:
            return ChartEncoding(x_field=x_field, y_field=y_field, series_field=resolved_series.name)
        return ChartEncoding(x_field=x_field, y_field=y_field)

    def _resolve_x_field(self, shape: ResultShape, semantics: QuerySemantics) -> str | None:
        if semantics.time and semantics.time.column and shape.column(semantics.time.column) is not None:
            return semantics.time.column
        candidates = shape.x_candidates()
        if shape.series_column is not None:
            candidates = [column for column in candidates if column.name != shape.series_column.name] or candidates
        if candidates:
            return candidates[0].name
        if shape.columns:
            return shape.columns[0].name
        return None

    def _resolve_y_field(self, shape: ResultShape, semantics: QuerySemantics) -> str | None:
        if semantics.metric and semantics.metric.name and shape.column(semantics.metric.name) is not None:
            return semantics.metric.name
        if semantics.flags.is_ranking or semantics.flags.is_share or semantics.intent == "share":
            rate_column = self._first_rate_like_numeric(shape)
            if rate_column is not None:
                return rate_column.name
        y_candidate = shape.y_candidate()
        if y_candidate is not None:
            return y_candidate.name
        return None

    @staticmethod
    def _first_rate_like_numeric(shape: ResultShape) -> ColumnInfo | None:
        rate_markers = ("rate", "share", "ratio", "conversion", "percent", "pct")
        for column in shape.numeric_columns:
            lowered = column.name.lower()
            if any(marker in lowered for marker in rate_markers):
                return column
        return None

    def _series_column_for_comparison(self, semantics: QuerySemantics, shape: ResultShape) -> ColumnInfo | None:
        if semantics.comparison and semantics.comparison.series_column:
            column = shape.column(semantics.comparison.series_column)
            if column is not None:
                return column
        if shape.series_column is not None:
            return shape.series_column
        candidates = [column for column in shape.categorical_columns if column.distinct_count <= 12]
        return candidates[0] if candidates else None

    def _is_shape_compatible(self, hinted_type: str, semantics: QuerySemantics, shape: ResultShape) -> bool:
        normalized = self._normalize_chart_type(hinted_type)
        if normalized == "table":
            return True
        if normalized == "metric_card":
            return shape.row_count == 1 and len(shape.numeric_columns) == 1
        if normalized == "pie":
            return bool(shape.categorical_columns and shape.numeric_columns and self._x_cardinality(shape, semantics) <= 6)
        if normalized == "line":
            return bool(shape.temporal_columns or semantics.flags.is_time_series)
        return bool(shape.x_candidates() and shape.numeric_columns)

    def _candidate_chart_type(self, shape: ResultShape) -> str:
        if shape.temporal_columns and shape.numeric_columns:
            return "line"
        if shape.categorical_columns and shape.numeric_columns:
            return "bar"
        if not shape.categorical_columns and len(shape.numeric_columns) == 1 and shape.row_count == 1:
            return "metric_card"
        if shape.categorical_columns and len(shape.numeric_columns) == 1 and self._x_cardinality_from_columns(shape.categorical_columns) <= 6:
            return "pie"
        return "table"

    def _x_cardinality(self, shape: ResultShape, semantics: QuerySemantics) -> int:
        x_field = self._resolve_x_field(shape, semantics)
        return shape.cardinality(x_field)

    def _x_cardinality_from_columns(self, columns: list[ColumnInfo]) -> int:
        return max((column.distinct_count for column in columns), default=0)

    def _normalize_chart_type(self, value: str) -> str:
        normalized = value.strip().lower()
        aliases = {
            "stacked_bar": "bar",
            "horizontal_bar": "bar",
            "metric": "metric_card",
            "kpi": "metric_card",
        }
        return aliases.get(normalized, normalized)

    def _reconcile_semantics_with_shape(self, semantics: QuerySemantics, shape: ResultShape) -> QuerySemantics:
        flags = semantics.flags
        needs_patch = False
        patched_flags_kwargs = flags.model_dump()
        if flags.is_time_series and not shape.temporal_columns:
            patched_flags_kwargs["is_time_series"] = False
            needs_patch = True
        if flags.is_comparison and shape.series_column is None:
            patched_flags_kwargs["is_comparison"] = False
            needs_patch = True
        if not flags.is_ranking and not shape.temporal_columns and shape.categorical_columns and shape.numeric_columns:
            if self._first_rate_like_numeric(shape) is not None and 0 < shape.row_count <= 50:
                patched_flags_kwargs["is_ranking"] = True
                needs_patch = True
        if not needs_patch:
            return semantics
        patched = semantics.model_copy(deep=True)
        patched.flags = SemanticFlagsPayload(**patched_flags_kwargs)
        return patched

    def _semantics_from_shape(self, shape: ResultShape) -> QuerySemantics:
        flags = SemanticFlagsPayload(
            is_time_series=bool(shape.temporal_columns),
            is_comparison=bool(shape.series_column),
        )
        time = None
        if shape.temporal_columns:
            time = SemanticTimePayload(column=shape.temporal_columns[0].name)
        comparison = None
        if shape.series_column is not None:
            comparison = SemanticComparisonPayload(kind="entity_vs_entity", series_column=shape.series_column.name)
        return QuerySemantics(
            intent=None,
            time=time,
            comparison=comparison,
            flags=flags,
        )
