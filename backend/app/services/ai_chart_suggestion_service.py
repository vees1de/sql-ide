from __future__ import annotations

from app.schemas.query import ChartSpec, QueryExecutionResult
from app.services.chart_decision_service import ChartDecisionService
from app.services.chart_spec_service import ChartSpecService
from app.services.llm_service import LLMChartSuggestionPayload, LLMService


class AIChartSuggestionUnavailableError(RuntimeError):
    pass


class AIChartSuggestionService:
    CHART_TYPE_ALIASES = {
        "kpi": "metric_card",
        "metric": "metric_card",
        "stacked_bar": "bar",
        "grouped_bar": "bar",
        "multi_line": "line",
    }
    SUPPORTED_CHART_TYPES = {"line", "bar", "pie", "metric_card", "table"}

    def __init__(self) -> None:
        self.chart_decision_service = ChartDecisionService()
        self.chart_spec_service = ChartSpecService()
        self.llm_service = LLMService()

    def suggest(
        self,
        *,
        goal: str,
        sql: str,
        columns: list[dict[str, str]],
        execution: QueryExecutionResult,
    ) -> ChartSpec:
        default_decision = self.chart_decision_service.decide(None, execution)
        default_spec = self.chart_spec_service.from_decision(
            execution,
            default_decision,
            title="Автоматическая визуализация",
        )
        payload = self.llm_service.suggest_chart(
            goal=goal,
            sql=sql,
            columns=columns,
            rows=execution.rows,
            row_count=execution.row_count,
            default_chart=default_spec.model_dump(mode="json"),
        )
        if payload is None:
            raise AIChartSuggestionUnavailableError("AI chart suggestion is unavailable.")

        decision = self._merge_with_default(default_decision, payload, execution)
        spec = self.chart_spec_service.from_decision(
            execution,
            decision,
            title=(payload.title or "AI suggestion").strip() or "AI suggestion",
        )
        spec.rule_id = "AI_SUGGESTION"
        return spec

    def _merge_with_default(self, default_decision, payload: LLMChartSuggestionPayload, execution: QueryExecutionResult):
        decision = default_decision.model_copy(deep=True)
        available_fields = {str(column) for column in execution.columns}
        if self._references_unknown_field(payload, available_fields):
            return default_decision.model_copy(deep=True)

        normalized_type = self._normalize_chart_type(payload.chart_type)
        if normalized_type in self.SUPPORTED_CHART_TYPES:
            decision.chart_type = normalized_type

        encoding = decision.encoding.model_copy(deep=True)
        if payload.x_field in available_fields:
            encoding.x_field = payload.x_field
        if payload.y_field in available_fields:
            encoding.y_field = payload.y_field
        if payload.series_field in available_fields:
            encoding.series_field = payload.series_field
        if payload.facet_field in available_fields:
            encoding.facet_field = payload.facet_field
        if payload.normalize in {"none", "percent", "index_100", "running_total"}:
            encoding.normalize = payload.normalize
        if payload.sort:
            encoding.sort = payload.sort

        decision.encoding = encoding
        decision.variant = self._resolve_variant(
            chart_type=decision.chart_type,
            suggested_variant=payload.variant,
            has_series=bool(encoding.series_field),
        )
        decision.reason = (payload.reason or default_decision.reason).strip()
        decision.explanation = (payload.explanation or decision.reason).strip()
        decision.confidence = self._clamp_confidence(payload.confidence, default_decision.confidence)
        decision.rule_id = "AI_SUGGESTION"

        if not self._has_required_fields(decision.chart_type, encoding.x_field, encoding.y_field):
            return default_decision.model_copy(deep=True)

        return decision

    def _normalize_chart_type(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = str(value).strip().lower()
        return self.CHART_TYPE_ALIASES.get(normalized, normalized)

    def _resolve_variant(self, *, chart_type: str, suggested_variant: str | None, has_series: bool) -> str:
        if chart_type == "table":
            return "table_only"
        if chart_type == "metric_card":
            return "single_value"
        if chart_type == "pie":
            return "share"
        if suggested_variant:
            return suggested_variant
        if chart_type == "line":
            return "multi_series" if has_series else "single_series"
        if chart_type == "bar":
            return "grouped" if has_series else "single_series"
        return "single_series"

    def _has_required_fields(self, chart_type: str, x_field: str | None, y_field: str | None) -> bool:
        if chart_type == "table":
            return True
        if chart_type == "metric_card":
            return bool(y_field)
        if chart_type == "pie":
            return bool(x_field and y_field)
        if chart_type in {"line", "bar"}:
            return bool(x_field and y_field)
        return False

    def _clamp_confidence(self, value: float | None, fallback: float) -> float:
        if value is None:
            return fallback
        return max(0.0, min(1.0, float(value)))

    def _references_unknown_field(self, payload: LLMChartSuggestionPayload, available_fields: set[str]) -> bool:
        for field in (payload.x_field, payload.y_field, payload.series_field, payload.facet_field):
            if field is not None and field not in available_fields:
                return True
        return False
