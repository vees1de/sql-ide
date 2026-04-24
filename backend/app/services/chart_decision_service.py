from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.query import (
    ChartCandidate,
    ChartEncoding,
    DecisionAlternative,
    DecisionSummary,
    QueryInterpretation,
    QueryInterpretationDimension,
    QueryInterpretationMetric,
    QueryExecutionResult,
    QuerySemantics,
    SemanticComparisonPayload,
    SemanticDataRolesPayload,
    SemanticFlagsPayload,
    SemanticTimePayload,
)


class ColumnInfo(BaseModel):
    name: str
    kind: Literal["temporal", "numeric", "categorical", "unknown"] = "unknown"
    distinct_count: int = 0
    non_null_count: int = 0
    avg_text_length: float = 0.0
    max_text_length: int = 0
    numeric_min: float | None = None
    numeric_max: float | None = None

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
    facet_column: ColumnInfo | None = None

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

    def has_negative_values(self, name: str | None) -> bool:
        column = self.column(name)
        return bool(column and column.numeric_min is not None and column.numeric_min < 0)

    def max_label_length(self, name: str | None) -> int:
        column = self.column(name)
        return column.max_text_length if column is not None else 0

    def x_candidates(self, exclude: set[str] | None = None) -> list[ColumnInfo]:
        excluded = exclude or set()
        temporal = [column for column in self.temporal_columns if column.name not in excluded]
        if temporal:
            return temporal
        return [column for column in self.categorical_columns if column.name not in excluded]

    def y_candidate(self) -> ColumnInfo | None:
        return self.numeric_columns[0] if self.numeric_columns else None

    def categorical_candidates(self, exclude: set[str] | None = None) -> list[ColumnInfo]:
        excluded = exclude or set()
        return [column for column in self.categorical_columns if column.name not in excluded]


class ChartDecision(BaseModel):
    chart_type: Literal["line", "bar", "pie", "metric_card", "table"]
    variant: str
    encoding: ChartEncoding = Field(default_factory=ChartEncoding)
    explanation: str
    reason: str
    rule_id: str
    confidence: float
    semantic_intent: str | None = None
    analysis_mode: str | None = None
    visual_goal: str | None = None
    time_role: str | None = None
    comparison_goal: str | None = None
    preferred_mark: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    candidates: list[ChartCandidate] = Field(default_factory=list)
    constraints_applied: list[str] = Field(default_factory=list)
    visual_load: int | None = None
    reason_codes: list[str] = Field(default_factory=list)
    query_interpretation: QueryInterpretation | None = None
    decision_summary: DecisionSummary | None = None


class DecisionCandidate(BaseModel):
    type: str
    chart_type: Literal["line", "bar", "pie", "metric_card", "table"]
    variant: str
    score: float
    why: str

    def exposed(self) -> ChartCandidate:
        return ChartCandidate(type=self.type, score=self.score, why=self.why)


@dataclass
class DecisionContext:
    semantics: QuerySemantics
    x_field: str | None
    y_field: str | None
    series_field: str | None
    facet_field: str | None
    semantic_intent: str
    analysis_mode: str
    visual_goal: str
    time_role: str
    comparison_goal: str
    preferred_mark: str
    has_time: bool
    single_value: bool
    share_like: bool
    ranking_like: bool
    delta_like: bool
    distribution_like: bool
    correlation_like: bool
    composition_like: bool
    direct_comparison: bool
    x_cardinality: int
    category_count: int
    series_count: int
    metric_count: int
    visual_load: int
    labels_long: bool
    few_periods: bool
    many_periods: bool
    series_limit: int | None
    category_limit: int | None
    top_n_strategy: Literal["top_plus_other", "top_only", "none"]
    value_format: str


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
        facet_column = self._detect_facet_column(categorical_columns, series_column)
        return ResultShape(
            row_count=execution.row_count,
            columns=columns,
            temporal_columns=temporal_columns,
            numeric_columns=numeric_columns,
            categorical_columns=categorical_columns,
            series_column=series_column,
            facet_column=facet_column,
        )

    def _analyse_column(self, name: str, sample_rows: list[dict[str, Any]]) -> ColumnInfo:
        values = [row.get(name) for row in sample_rows if row.get(name) is not None]
        distinct_values = {self._normalize_value(value) for value in values}
        distinct_values.discard(None)
        numeric_values = [number for value in values if (number := self._maybe_number(value)) is not None]
        text_lengths = [len(str(value)) for value in values]
        kind = self._classify_kind(name, values)
        return ColumnInfo(
            name=name,
            kind=kind,
            distinct_count=len(distinct_values),
            non_null_count=len(values),
            avg_text_length=(sum(text_lengths) / len(text_lengths)) if text_lengths else 0.0,
            max_text_length=max(text_lengths, default=0),
            numeric_min=min(numeric_values) if numeric_values else None,
            numeric_max=max(numeric_values) if numeric_values else None,
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
        numeric = sum(1 for value in values if self._maybe_number(value) is not None)
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
                if column.name in {"comparison_series", "series"} or column.name.endswith("_series")
            ),
            None,
        )
        if preferred is not None:
            return preferred

        candidates = [
            column
            for column in categorical_columns
            if 2 <= column.distinct_count <= 12 and not self._looks_like_entity_id(column)
        ]
        if temporal_columns and candidates:
            return sorted(candidates, key=lambda column: (column.distinct_count, column.max_text_length))[0]
        if len(candidates) >= 2:
            return sorted(candidates, key=lambda column: (column.distinct_count, column.max_text_length))[0]
        if candidates:
            return candidates[0]
        return None

    def _detect_facet_column(
        self,
        categorical_columns: list[ColumnInfo],
        series_column: ColumnInfo | None,
    ) -> ColumnInfo | None:
        candidates = [
            column
            for column in categorical_columns
            if column is not series_column and 2 <= column.distinct_count <= 8 and not self._looks_like_entity_id(column)
        ]
        return sorted(candidates, key=lambda column: (column.distinct_count, column.max_text_length))[0] if candidates else None

    def _looks_like_entity_id(self, column: ColumnInfo) -> bool:
        lowered = column.name.lower()
        return lowered.endswith("_id") or lowered == "id"

    def _maybe_number(self, value: Any) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "."))
        except Exception:
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
    MAX_SERIES = 5
    MAX_CATEGORIES = 10
    DIRECT_COMPARISON_INTENTS = {"comparison", "comparison_over_time", "ranking", "delta"}

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
        reconciled = self._reconcile_semantics_with_shape(semantics, shape)
        context = self._build_context(reconciled, shape)
        candidates = self._score_candidates(context, shape)
        if not candidates:
            candidates = [self._candidate_for_type("table", 0.6, "Для этого набора данных безопаснее оставить табличный вывод.")]
        selected, constraints = self._post_validate(candidates[0], context, shape)
        ranked = self._with_selected_first(selected, candidates)
        encoding = self._build_encoding(selected, context, shape)
        alternatives = [candidate.type for candidate in ranked[1:3]]
        explanation = selected.why
        if constraints:
            explanation = f"{selected.why} Ограничения: {'; '.join(constraints)}."
        reason_codes = self._build_reason_codes(context, constraints)
        query_interpretation = self._build_query_interpretation(context, selected)
        decision_summary = DecisionSummary(
            selected_chart=selected.type,
            why=explanation,
            reason_codes=reason_codes,
            alternatives=[
                DecisionAlternative(type=c.type, why_not=c.why)
                for c in ranked[1:3]
            ],
            confidence=selected.score,
        )
        return ChartDecision(
            chart_type=selected.chart_type,
            variant=selected.variant,
            encoding=encoding,
            explanation=explanation,
            reason=selected.why,
            rule_id=f"CASCADE_{selected.type.upper()}",
            confidence=selected.score,
            semantic_intent=context.semantic_intent,
            analysis_mode=context.analysis_mode,
            visual_goal=context.visual_goal,
            time_role=context.time_role,
            comparison_goal=context.comparison_goal,
            preferred_mark=selected.chart_type if selected.chart_type != "metric_card" else "stat",
            alternatives=alternatives,
            candidates=[candidate.exposed() for candidate in ranked[:3]],
            constraints_applied=constraints,
            visual_load=context.visual_load,
            reason_codes=reason_codes,
            query_interpretation=query_interpretation,
            decision_summary=decision_summary,
        )

    def _build_context(self, semantics: QuerySemantics, shape: ResultShape) -> DecisionContext:
        x_field = self._resolve_x_field(shape, semantics)
        y_field = self._resolve_y_field(shape, semantics)
        series_field = self._resolve_series_field(shape, semantics, x_field)
        facet_field = self._resolve_facet_field(shape, semantics, x_field, series_field)
        has_time = bool(shape.temporal_columns and (shape.column(x_field).is_temporal if shape.column(x_field) else True))
        semantic_intent = self._resolve_semantic_intent(semantics, shape, has_time, series_field)
        analysis_mode = self._resolve_analysis_mode(semantics, semantic_intent)
        comparison_goal = self._resolve_comparison_goal(semantics, analysis_mode, semantic_intent)
        visual_goal = self._resolve_visual_goal(semantics, semantic_intent, comparison_goal, has_time, series_field)
        category_count = shape.cardinality(x_field)
        series_count = shape.cardinality(series_field) if series_field else 0
        x_cardinality = shape.cardinality(x_field)
        metric_count = len(shape.numeric_columns)
        labels_long = shape.max_label_length(x_field) > 16
        single_value = shape.row_count == 1 and metric_count == 1 and not shape.categorical_columns
        share_like = semantic_intent in {"share", "composition_over_time"} or comparison_goal == "composition" or semantics.flags.is_share
        ranking_like = semantic_intent == "ranking" or comparison_goal == "rank" or semantics.flags.is_ranking
        delta_like = semantic_intent == "delta" or analysis_mode == "delta" or comparison_goal == "delta"
        distribution_like = semantic_intent == "distribution"
        correlation_like = semantic_intent == "correlation"
        composition_like = share_like or semantic_intent == "composition_over_time"
        direct_comparison = semantic_intent in self.DIRECT_COMPARISON_INTENTS or analysis_mode in {"compare", "rank", "delta"}
        visual_load = max(1, x_cardinality or category_count or shape.row_count) * max(1, series_count or 1)
        few_periods = has_time and 0 < x_cardinality <= 8
        many_periods = has_time and x_cardinality > 8
        series_limit = self.MAX_SERIES if series_count > self.MAX_SERIES else None
        category_limit = self.MAX_CATEGORIES if not has_time and category_count > self.MAX_CATEGORIES else None
        top_n_strategy: Literal["top_plus_other", "top_only", "none"] = (
            "top_plus_other" if (series_limit or category_limit) else "none"
        )
        return DecisionContext(
            semantics=semantics,
            x_field=x_field,
            y_field=y_field,
            series_field=series_field,
            facet_field=facet_field,
            semantic_intent=semantic_intent,
            analysis_mode=analysis_mode,
            visual_goal=visual_goal,
            time_role=self._resolve_time_role(semantics, has_time),
            comparison_goal=comparison_goal,
            preferred_mark=self._resolve_preferred_mark(semantics, semantic_intent, has_time, share_like),
            has_time=has_time,
            single_value=single_value,
            share_like=share_like,
            ranking_like=ranking_like,
            delta_like=delta_like,
            distribution_like=distribution_like,
            correlation_like=correlation_like,
            composition_like=composition_like,
            direct_comparison=direct_comparison,
            x_cardinality=x_cardinality,
            category_count=category_count,
            series_count=series_count,
            metric_count=metric_count,
            visual_load=visual_load,
            labels_long=labels_long,
            few_periods=few_periods,
            many_periods=many_periods,
            series_limit=series_limit,
            category_limit=category_limit,
            top_n_strategy=top_n_strategy,
            value_format=self._infer_value_format(y_field),
        )

    def _score_candidates(self, context: DecisionContext, shape: ResultShape) -> list[DecisionCandidate]:
        ranked: dict[str, DecisionCandidate] = {}

        def register(candidate_type: str, score: float, why: str) -> None:
            candidate = self._candidate_for_type(candidate_type, score + self._hint_bonus(context, candidate_type), why)
            current = ranked.get(candidate.type)
            if current is None or candidate.score > current.score:
                ranked[candidate.type] = candidate

        if context.single_value:
            register("metric_card", 0.99, "В результате одна числовая величина без осей, поэтому нужен KPI card.")
            register("table", 0.42, "Таблица возможна, но KPI card передает запрос точнее.")
            return sorted(ranked.values(), key=lambda item: item.score, reverse=True)

        if shape.row_count == 0:
            register("table", 1.0, "Нет данных для визуализации.")
            return sorted(ranked.values(), key=lambda item: item.score, reverse=True)

        if context.correlation_like:
            register("table", 0.74, "Запрос похож на корреляцию, а scatter пока не поддержан как базовый renderer.")

        if context.distribution_like:
            register("bar", 0.78, "Для распределения по одному числовому признаку histogram-like bar chart читается лучше всего.")
            register("table", 0.55, "Таблица может быть запасным вариантом для распределения.")

        if context.has_time and context.series_count <= 1:
            register(
                "line",
                0.9 if context.analysis_mode in {"trend", "delta"} or context.semantic_intent == "trend" else 0.8,
                "Есть временная ось и одна серия, поэтому линия лучше всего сохраняет форму динамики.",
            )
            if context.few_periods:
                register(
                    "bar",
                    0.74 if context.semantic_intent != "trend" else 0.66,
                    "Периодов немного, поэтому bar chart еще остается читаемым для сравнения значений по времени.",
                )

        if context.has_time and context.series_count >= 2:
            if context.composition_like:
                register(
                    "stacked_bar",
                    0.9 if context.few_periods else 0.76,
                    "Есть время и вторичная категория, а цель похожа на composition/share, поэтому stacked bar подходит лучше.",
                )
            if context.series_count <= self.MAX_SERIES:
                register(
                    "grouped_bar",
                    0.93 if context.few_periods and context.direct_comparison else 0.73,
                    "Есть время и вторичная категория; при небольшом числе периодов grouped bar лучше сохраняет сравнение внутри периода.",
                )
                register(
                    "multi_line",
                    0.94 if context.many_periods else 0.82,
                    "Есть время и несколько серий; при более длинной оси времени multi-line масштабируется лучше grouped bar.",
                )
            else:
                register(
                    "multi_line",
                    0.88 if context.many_periods else 0.76,
                    "Есть много серий во времени; multi-line остается лучшим кандидатом только с top-N или facet strategy.",
                )
                register(
                    "table",
                    0.72 if context.visual_load > 40 else 0.57,
                    "Визуальная плотность высокая, поэтому таблица может быть безопаснее шумного графика.",
                )

        if context.share_like:
            if not context.has_time and 0 < context.category_count <= 6:
                register("pie", 0.9, "Небольшое число категорий и задача на доли допускают donut/pie chart.")
            elif not context.has_time and context.semantics.visualization_hint == "pie":
                register("pie", 0.82, "Pie chart был явно запрошен, поэтому он добавлен как кандидат и будет проверен валидатором.")
            register(
                "bar_horizontal",
                0.71,
                "Даже для долей horizontal bar сохраняет более точное визуальное сравнение между категориями.",
            )

        if context.ranking_like:
            register(
                "bar_horizontal_sorted",
                0.95,
                "Запрос похож на ranking/top-N, поэтому нужен отсортированный horizontal bar chart.",
            )
            register("table", 0.61, "Таблица может быть fallback для длинного рейтинга.")

        if context.semantic_intent in {"comparison", "comparison_over_time"} or context.analysis_mode == "compare":
            if not context.has_time:
                if context.series_count >= 2:
                    register(
                        "grouped_bar",
                        0.91 if not context.composition_like else 0.76,
                        "Сравнение между категориями и несколькими сериями лучше всего сохраняется в grouped bar.",
                    )
                    if context.composition_like:
                        register(
                            "stacked_bar",
                            0.83,
                            "Если важна структура внутри категории, stacked bar может быть второй опцией.",
                        )
                else:
                    register(
                        "bar_horizontal" if (context.labels_long or context.category_count > 5) else "bar",
                        0.88,
                        "Без времени и без множества серий bar chart лучше всего поддерживает прямое сравнение категорий.",
                    )

        if context.visual_load > 24:
            register(
                "table",
                0.88,
                "Визуальная плотность слишком высокая для надежного графика, поэтому таблица становится полноценным fallback.",
            )

        if not ranked:
            if context.has_time:
                register("line", 0.72, "Есть временная ось, поэтому line chart является безопасным базовым выбором.")
            elif context.category_count and context.metric_count:
                register(
                    "bar_horizontal" if context.labels_long or context.category_count > 5 else "bar",
                    0.7,
                    "Категория и метрика без времени обычно лучше всего читаются в bar chart.",
                )
            register("table", 0.58, "Таблица остается универсальным fallback.")

        return sorted(ranked.values(), key=lambda item: item.score, reverse=True)

    def _post_validate(
        self,
        selected: DecisionCandidate,
        context: DecisionContext,
        shape: ResultShape,
    ) -> tuple[DecisionCandidate, list[str]]:
        constraints: list[str] = []
        candidate = selected

        if candidate.type == "pie":
            if context.has_time:
                constraints.append("pie_forbidden_with_time_axis")
                candidate = self._candidate_for_type(
                    "stacked_bar" if context.composition_like and context.series_count >= 2 else "bar_horizontal",
                    candidate.score - 0.05,
                    "Pie отклонен: при наличии времени он скрывает динамику, поэтому выбран bar-based fallback.",
                )
            elif context.category_count > 6:
                constraints.append("pie_forbidden_above_six_categories")
                candidate = self._candidate_for_type(
                    "bar_horizontal_sorted" if context.ranking_like else "bar_horizontal",
                    candidate.score - 0.05,
                    "Pie отклонен: категорий слишком много для надежного сравнения долей.",
                )
            elif shape.has_negative_values(context.y_field):
                constraints.append("pie_forbidden_with_negative_values")
                candidate = self._candidate_for_type(
                    "bar_horizontal",
                    candidate.score - 0.05,
                    "Pie отклонен: отрицательные значения не подходят для секторной диаграммы.",
                )
            elif context.direct_comparison and not context.composition_like:
                constraints.append("pie_forbidden_for_direct_comparison")
                candidate = self._candidate_for_type(
                    "bar_horizontal_sorted",
                    candidate.score - 0.05,
                    "Pie отклонен: запрос требует прямого сравнения между категориями.",
                )

        if candidate.type in {"line", "multi_line"} and not context.has_time:
            constraints.append("line_forbidden_without_ordered_time_axis")
            candidate = self._candidate_for_type(
                "grouped_bar" if context.series_count >= 2 else "bar_horizontal",
                candidate.score - 0.06,
                "Line отклонен: ось X не является упорядоченной временной осью.",
            )

        if candidate.type == "stacked_bar":
            if not context.composition_like:
                constraints.append("stacked_bar_forbidden_for_precise_cross_series_comparison")
                candidate = self._candidate_for_type(
                    "grouped_bar",
                    candidate.score - 0.04,
                    "Stacked bar отклонен: здесь важнее точное сравнение серий, а не состав.",
                )
            elif context.series_count > 8:
                constraints.append("stacked_bar_forbidden_with_too_many_segments")
                candidate = self._candidate_for_type(
                    "table",
                    candidate.score - 0.06,
                    "Stacked bar отклонен: слишком много сегментов для читаемого сравнения.",
                )

        if candidate.type == "grouped_bar":
            if context.series_count <= 1:
                constraints.append("grouped_bar_degrades_without_multiple_series")
                candidate = self._candidate_for_type(
                    "bar" if not context.has_time else ("line" if context.many_periods else "bar"),
                    candidate.score - 0.03,
                    "Grouped bar упрощен: в данных фактически одна серия.",
                )
            elif context.visual_load > 25:
                constraints.append("grouped_bar_forbidden_above_visual_density_threshold")
                candidate = self._candidate_for_type(
                    "multi_line" if context.has_time and context.series_count <= self.MAX_SERIES else "table",
                    candidate.score - 0.05,
                    "Grouped bar отклонен: визуальная плотность слишком высокая для читаемого сравнения.",
                )
            elif context.labels_long and context.series_count > 4:
                constraints.append("grouped_bar_forbidden_with_long_labels_and_many_series")
                candidate = self._candidate_for_type(
                    "table" if context.visual_load > 20 else "bar_horizontal",
                    candidate.score - 0.04,
                    "Grouped bar отклонен: длинные подписи и много серий делают график шумным.",
                )

        if candidate.type == "multi_line" and context.series_count > self.MAX_SERIES:
            constraints.append("multi_line_trimmed_to_top_n_plus_other")
            if context.facet_field:
                constraints.append("facet_key_selected_for_future_small_multiples")

        if candidate.type in {"bar", "bar_horizontal", "bar_horizontal_sorted"} and context.has_time and context.many_periods:
            constraints.append("bar_degrades_on_long_time_axis")
            candidate = self._candidate_for_type(
                "line",
                candidate.score - 0.04,
                "Bar отклонен: длинная временная ось лучше читается в line chart.",
            )

        return candidate, constraints

    def _build_encoding(self, selected: DecisionCandidate, context: DecisionContext, shape: ResultShape) -> ChartEncoding:
        series_field = context.series_field if selected.type in {"multi_line", "grouped_bar", "stacked_bar"} else None
        facet_field = context.facet_field if context.facet_field and (context.series_limit or context.visual_load > 24) else None
        data_roles = SemanticDataRolesPayload(
            x=context.x_field,
            y=context.y_field,
            series_key=series_field,
            facet_key=facet_field,
            label=context.x_field,
            value=context.y_field,
        )
        if selected.chart_type == "metric_card":
            return ChartEncoding(
                y_field=context.y_field or (shape.y_candidate().name if shape.y_candidate() else None),
                value_format=context.value_format,
                data_roles=data_roles,
            )
        return ChartEncoding(
            x_field=context.x_field,
            y_field=context.y_field,
            series_field=series_field,
            facet_field=facet_field,
            sort="time_asc" if context.has_time else ("value_desc" if context.ranking_like else None),
            normalize="percent" if selected.type == "pie" or (selected.type == "stacked_bar" and context.composition_like) else "none",
            series_limit=context.series_limit if series_field else None,
            category_limit=context.category_limit,
            top_n_strategy=context.top_n_strategy,
            value_format=context.value_format,
            data_roles=data_roles,
        )

    def _resolve_x_field(self, shape: ResultShape, semantics: QuerySemantics) -> str | None:
        roles = semantics.data_roles
        if roles and roles.x and shape.column(roles.x) is not None:
            return roles.x
        if semantics.time and semantics.time.column and shape.column(semantics.time.column) is not None:
            return semantics.time.column
        excluded: set[str] = set()
        if roles and roles.series_key:
            excluded.add(roles.series_key)
        if roles and roles.facet_key:
            excluded.add(roles.facet_key)
        candidates = shape.x_candidates(excluded=excluded)
        if candidates:
            return candidates[0].name
        if shape.columns:
            return shape.columns[0].name
        return None

    def _resolve_y_field(self, shape: ResultShape, semantics: QuerySemantics) -> str | None:
        is_rate_query = (
            semantics.flags.is_ranking
            or semantics.flags.is_share
            or semantics.intent == "share"
            or semantics.intent == "ranking"
        )
        rate_markers = ("rate", "share", "ratio", "conversion", "percent", "pct")

        def _is_rate_like(col_name: str) -> bool:
            return any(marker in col_name.lower() for marker in rate_markers)

        # For ranking/share queries, prefer a rate column even if roles.y is set to a non-rate column.
        if is_rate_query:
            rate_column = self._first_rate_like_numeric(shape)
            if rate_column is not None:
                return rate_column.name

        roles = semantics.data_roles
        if roles and roles.y and shape.column(roles.y) is not None:
            return roles.y
        if semantics.metric and semantics.metric.name and shape.column(semantics.metric.name) is not None:
            return semantics.metric.name
        y_candidate = shape.y_candidate()
        return y_candidate.name if y_candidate is not None else None

    def _resolve_series_field(self, shape: ResultShape, semantics: QuerySemantics, x_field: str | None) -> str | None:
        roles = semantics.data_roles
        if roles and roles.series_key and shape.column(roles.series_key) is not None and roles.series_key != x_field:
            return roles.series_key
        if semantics.comparison and semantics.comparison.series_column:
            column = shape.column(semantics.comparison.series_column)
            if column is not None and column.name != x_field:
                return column.name
        if shape.series_column is not None and shape.series_column.name != x_field:
            return shape.series_column.name
        candidates = [column for column in shape.categorical_candidates(exclude={x_field} if x_field else set()) if column.distinct_count <= 12]
        return candidates[0].name if candidates else None

    def _resolve_facet_field(
        self,
        shape: ResultShape,
        semantics: QuerySemantics,
        x_field: str | None,
        series_field: str | None,
    ) -> str | None:
        roles = semantics.data_roles
        if roles and roles.facet_key and shape.column(roles.facet_key) is not None:
            return roles.facet_key
        if semantics.comparison and semantics.comparison.facet_column:
            column = shape.column(semantics.comparison.facet_column)
            if column is not None:
                return column.name
        if shape.facet_column is not None and shape.facet_column.name not in {x_field, series_field}:
            return shape.facet_column.name
        candidates = shape.categorical_candidates(exclude={name for name in {x_field, series_field} if name})
        return candidates[0].name if candidates else None

    def _resolve_semantic_intent(
        self,
        semantics: QuerySemantics,
        shape: ResultShape,
        has_time: bool,
        series_field: str | None,
    ) -> str:
        if semantics.intent:
            return semantics.intent
        if shape.row_count == 1 and len(shape.numeric_columns) == 1 and not shape.categorical_columns:
            return "kpi"
        if semantics.flags.is_ranking:
            return "ranking"
        if semantics.flags.is_share:
            return "composition_over_time" if has_time else "share"
        if semantics.comparison and semantics.comparison.kind == "period_over_period":
            return "delta"
        if has_time and (semantics.flags.is_comparison or bool(series_field)):
            return "comparison_over_time"
        if has_time:
            return "trend"
        if len(shape.numeric_columns) >= 2 and not shape.temporal_columns:
            return "correlation"
        if len(shape.numeric_columns) == 1 and not shape.categorical_columns and shape.row_count > 3:
            return "distribution"
        if semantics.flags.is_comparison or bool(series_field):
            return "comparison"
        return "comparison"

    def _resolve_analysis_mode(self, semantics: QuerySemantics, semantic_intent: str) -> str:
        if semantics.analysis_mode:
            return semantics.analysis_mode
        mapping = {
            "trend": "trend",
            "comparison": "compare",
            "comparison_over_time": "compare",
            "share": "compose",
            "composition_over_time": "compose",
            "ranking": "rank",
            "correlation": "correlate",
            "distribution": "distribute",
            "delta": "delta",
            "kpi": "compare",
        }
        return mapping.get(semantic_intent, "compare")

    def _resolve_time_role(self, semantics: QuerySemantics, has_time: bool) -> str:
        if semantics.time_role:
            return semantics.time_role
        return "primary" if has_time else "none"

    def _resolve_comparison_goal(self, semantics: QuerySemantics, analysis_mode: str, semantic_intent: str) -> str:
        if semantics.comparison_goal:
            return semantics.comparison_goal
        if analysis_mode == "rank" or semantic_intent == "ranking":
            return "rank"
        if analysis_mode == "compose" or semantic_intent in {"share", "composition_over_time"}:
            return "composition"
        if analysis_mode == "delta" or semantic_intent == "delta":
            return "delta"
        return "absolute"

    def _resolve_visual_goal(
        self,
        semantics: QuerySemantics,
        semantic_intent: str,
        comparison_goal: str,
        has_time: bool,
        series_field: str | None,
    ) -> str:
        if semantics.visual_goal:
            return semantics.visual_goal
        if semantic_intent == "kpi":
            return "single_value"
        if semantic_intent == "trend":
            return "show_change_over_time"
        if semantic_intent == "comparison_over_time":
            return "compare_between_groups_over_time" if series_field else "compare_periods"
        if semantic_intent in {"share", "composition_over_time"}:
            return "compare_structure_over_time" if has_time else "show_composition"
        if comparison_goal == "rank":
            return "compare_ranked_categories"
        if semantic_intent == "delta":
            return "compare_deltas_between_periods"
        if semantic_intent == "correlation":
            return "show_relationship_between_metrics"
        if semantic_intent == "distribution":
            return "show_distribution"
        return "compare_between_groups" if series_field else "compare_categories"

    def _resolve_preferred_mark(
        self,
        semantics: QuerySemantics,
        semantic_intent: str,
        has_time: bool,
        share_like: bool,
    ) -> str:
        if semantics.preferred_mark:
            return semantics.preferred_mark
        if semantic_intent == "kpi":
            return "stat"
        if share_like and not has_time:
            return "arc"
        if has_time:
            return "line"
        return "bar"

    @staticmethod
    def _first_rate_like_numeric(shape: ResultShape) -> ColumnInfo | None:
        rate_markers = ("rate", "share", "ratio", "conversion", "percent", "pct")
        for column in shape.numeric_columns:
            lowered = column.name.lower()
            if any(marker in lowered for marker in rate_markers):
                return column
        return None

    def _candidate_for_type(self, candidate_type: str, score: float, why: str) -> DecisionCandidate:
        mapping: dict[str, tuple[Literal["line", "bar", "pie", "metric_card", "table"], str]] = {
            "metric_card": ("metric_card", "single_kpi"),
            "line": ("line", "single_series"),
            "multi_line": ("line", "multi_series"),
            "bar": ("bar", "single_series"),
            "grouped_bar": ("bar", "grouped"),
            "stacked_bar": ("bar", "stacked"),
            "bar_horizontal": ("bar", "horizontal"),
            "bar_horizontal_sorted": ("bar", "horizontal_sorted"),
            "pie": ("pie", "donut"),
            "table": ("table", "default"),
        }
        chart_type, variant = mapping[candidate_type]
        return DecisionCandidate(
            type=candidate_type,
            chart_type=chart_type,
            variant=variant,
            score=max(0.0, min(score, 0.99)),
            why=why,
        )

    def _hint_bonus(self, context: DecisionContext, candidate_type: str) -> float:
        if not context.semantics.visualization_hint:
            return 0.0
        hinted = self._normalize_chart_type(context.semantics.visualization_hint)
        if hinted == "metric_card" and candidate_type == "metric_card":
            return 0.04
        if hinted == "pie" and candidate_type == "pie":
            return 0.04
        if hinted == "line" and candidate_type in {"line", "multi_line"}:
            return 0.03
        if hinted == "bar" and candidate_type in {"bar", "grouped_bar", "stacked_bar", "bar_horizontal", "bar_horizontal_sorted"}:
            return 0.03
        if hinted == "table" and candidate_type == "table":
            return 0.03
        return 0.0

    def _with_selected_first(
        self,
        selected: DecisionCandidate,
        ranked: list[DecisionCandidate],
    ) -> list[DecisionCandidate]:
        merged = [selected]
        seen = {selected.type}
        for candidate in ranked:
            if candidate.type in seen:
                continue
            merged.append(candidate)
            seen.add(candidate.type)
        return merged

    def _build_reason_codes(self, context: DecisionContext, constraints: list[str]) -> list[str]:
        codes = [f"INTENT_{context.semantic_intent.upper()}"]
        if context.has_time:
            codes.append("HAS_TIME_AXIS")
        if context.series_count >= 2:
            codes.append("HAS_SECONDARY_DIMENSION")
        if context.analysis_mode == "compare":
            codes.append("COMPARISON_PRIMARY_GOAL")
        elif context.analysis_mode == "compose":
            codes.append("COMPOSITION_PRIMARY_GOAL")
        elif context.analysis_mode == "rank":
            codes.append("RANKING_PRIMARY_GOAL")
        elif context.analysis_mode == "delta":
            codes.append("DELTA_PRIMARY_GOAL")
        elif context.analysis_mode == "trend":
            codes.append("TREND_PRIMARY_GOAL")
        if context.few_periods:
            codes.append("FEW_TIME_BUCKETS")
        if context.many_periods:
            codes.append("MANY_TIME_BUCKETS")
        if 0 < context.series_count <= self.MAX_SERIES:
            codes.append("SERIES_COUNT_ACCEPTABLE")
        if context.series_count > self.MAX_SERIES:
            codes.append("SERIES_COUNT_HIGH")
        if context.visual_load > 24:
            codes.append("VISUAL_LOAD_HIGH")
        elif context.visual_load > 12:
            codes.append("VISUAL_LOAD_MEDIUM")
        if context.top_n_strategy == "top_plus_other":
            codes.append("LIMIT_TOP_N_PLUS_OTHER")
        codes.extend(f"CONSTRAINT_{constraint.upper()}" for constraint in constraints)
        return codes

    def _build_query_interpretation(
        self,
        context: DecisionContext,
        selected: DecisionCandidate,
    ) -> QueryInterpretation:
        metric_name = context.y_field or (context.semantics.metric.name if context.semantics.metric else None) or "metric"
        dimensions: list[QueryInterpretationDimension] = []
        if context.x_field:
            dimensions.append(
                QueryInterpretationDimension(
                    name=context.x_field,
                    role="time" if context.time_role == "primary" else "category",
                )
            )
        if context.series_field:
            dimensions.append(QueryInterpretationDimension(name=context.series_field, role="series"))
        if context.facet_field:
            dimensions.append(QueryInterpretationDimension(name=context.facet_field, role="facet"))

        assumptions = list(dict.fromkeys(context.semantics.assumptions))
        ambiguities = list(dict.fromkeys(context.semantics.ambiguities))

        aggregation = context.semantics.metric.aggregation if context.semantics.metric else None
        if metric_name and aggregation:
            assumptions.append(f"Metric '{metric_name}' is aggregated using {aggregation}.")
        if context.series_limit or context.category_limit:
            assumptions.append("If cardinality is too high, the chart will use top-N plus Other.")
        if context.semantic_intent in {"share", "composition_over_time"} and selected.type in {"stacked_bar", "pie"}:
            assumptions.append("Composition is interpreted as share of the total.")
        if context.has_time and not context.semantics.time:
            ambiguities.append("Time range was not explicitly specified in the interpretation.")
        assumptions = list(dict.fromkeys(assumptions))
        ambiguities = list(dict.fromkeys(ambiguities))

        return QueryInterpretation(
            user_goal=self._summarize_user_goal(context),
            intent=context.semantic_intent,
            analysis_mode=context.analysis_mode,
            entities=list(context.semantics.comparison.entities) if context.semantics.comparison else [],
            metrics=[
                QueryInterpretationMetric(
                    name=metric_name,
                    aggregation=aggregation,
                    format=context.value_format,
                )
            ],
            dimensions=dimensions,
            time_dimension=context.x_field if context.time_role == "primary" else None,
            series_dimension=context.series_field,
            requested_output="stat" if selected.chart_type == "metric_card" else ("table" if selected.chart_type == "table" else "chart"),
            assumptions=assumptions,
            ambiguities=ambiguities,
            confidence=max(context.semantics.confidence_score or 0.0, selected.score),
            short_explanation=selected.why,
        )

    def _summarize_user_goal(self, context: DecisionContext) -> str:
        verb = {
            "compare": "Compare",
            "trend": "Track",
            "compose": "Show composition of",
            "rank": "Rank",
            "correlate": "Relate",
            "distribute": "Show distribution of",
            "delta": "Compare change in",
        }.get(context.analysis_mode, "Analyze")
        metric_name = context.y_field or "metric"
        parts = [f"{verb} {metric_name}"]
        if context.x_field:
            parts.append(f"by {context.x_field}")
        if context.series_field:
            parts.append(f"split by {context.series_field}")
        if context.facet_field:
            parts.append(f"faceted by {context.facet_field}")
        return " ".join(parts)

    def _normalize_chart_type(self, value: str) -> str:
        normalized = value.strip().lower()
        aliases = {
            "stacked_bar": "bar",
            "horizontal_bar": "bar",
            "metric": "metric_card",
            "kpi": "metric_card",
            "donut": "pie",
        }
        return aliases.get(normalized, normalized)

    def _infer_value_format(self, field: str | None) -> str:
        lowered = (field or "").lower()
        if any(token in lowered for token in ("revenue", "sales", "amount", "price", "cost", "gmv")):
            return "currency_compact"
        if any(token in lowered for token in ("rate", "share", "ratio", "percent", "pct", "conversion")):
            return "percent"
        if any(token in lowered for token in ("count", "orders", "qty", "quantity", "users")):
            return "integer_compact"
        return "number_compact"

    def _reconcile_semantics_with_shape(self, semantics: QuerySemantics, shape: ResultShape) -> QuerySemantics:
        patched = semantics.model_copy(deep=True)
        flags = patched.flags.model_dump()
        if flags["is_time_series"] and not shape.temporal_columns:
            flags["is_time_series"] = False
        if flags["is_comparison"] and shape.series_column is None:
            flags["is_comparison"] = False
        if (
            not flags["is_ranking"]
            and not flags["is_share"]
            and semantics.intent not in {"share", "composition_over_time"}
            and semantics.comparison_goal != "composition"
            and not shape.temporal_columns
            and shape.categorical_columns
            and shape.numeric_columns
        ):
            if self._first_rate_like_numeric(shape) is not None and 0 < shape.row_count <= 50:
                flags["is_ranking"] = True
        patched.flags = SemanticFlagsPayload(**flags)
        if patched.time and patched.time.column and shape.column(patched.time.column) is None:
            patched.time = None
        if patched.data_roles is not None:
            patched.data_roles = SemanticDataRolesPayload(
                x=patched.data_roles.x if shape.column(patched.data_roles.x) is not None else None,
                y=patched.data_roles.y if shape.column(patched.data_roles.y) is not None else None,
                series_key=patched.data_roles.series_key if shape.column(patched.data_roles.series_key) is not None else None,
                facet_key=patched.data_roles.facet_key if shape.column(patched.data_roles.facet_key) is not None else None,
                label=patched.data_roles.label if shape.column(patched.data_roles.label) is not None else None,
                value=patched.data_roles.value if shape.column(patched.data_roles.value) is not None else None,
            )
        return patched

    def _semantics_from_shape(self, shape: ResultShape) -> QuerySemantics:
        flags = SemanticFlagsPayload(
            is_time_series=bool(shape.temporal_columns),
            is_comparison=bool(shape.series_column),
        )
        time = SemanticTimePayload(column=shape.temporal_columns[0].name) if shape.temporal_columns else None
        comparison = None
        if shape.series_column is not None:
            comparison = SemanticComparisonPayload(
                kind="entity_vs_entity",
                series_column=shape.series_column.name,
                facet_column=shape.facet_column.name if shape.facet_column is not None else None,
            )
        x_field = shape.temporal_columns[0].name if shape.temporal_columns else (shape.categorical_columns[0].name if shape.categorical_columns else None)
        y_field = shape.numeric_columns[0].name if shape.numeric_columns else None
        return QuerySemantics(
            intent=None,
            time=time,
            comparison=comparison,
            flags=flags,
            data_roles=SemanticDataRolesPayload(
                x=x_field,
                y=y_field,
                series_key=shape.series_column.name if shape.series_column is not None else None,
                facet_key=shape.facet_column.name if shape.facet_column is not None else None,
                label=x_field,
                value=y_field,
            ),
        )
