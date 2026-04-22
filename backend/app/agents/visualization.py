from __future__ import annotations

from app.schemas.query import ChartEncoding, ChartSpec, IntentPayload, QueryExecutionResult, SemanticMappingPayload


class VisualizationAgent:
    def run(
        self,
        intent: IntentPayload,
        semantic: SemanticMappingPayload,
        execution: QueryExecutionResult,
    ) -> ChartSpec:
        if not execution.rows:
            return ChartSpec(
                chart_type="table",
                title="No data",
                encoding=ChartEncoding(),
                options={"emptyState": True},
            )

        if intent.visualization_preference:
            chart_type = intent.visualization_preference
        elif self._is_distribution_query(intent):
            chart_type = "pie"
        elif self._is_temporal_query(intent):
            chart_type = "line"
        elif semantic.dimension_mappings and semantic.dimension_mappings[0].key in {"day", "week", "month"}:
            chart_type = "line"
        elif len(semantic.dimension_mappings) == 1:
            chart_type = "bar"
        elif not semantic.dimension_mappings:
            chart_type = "metric_card"
        else:
            chart_type = "table"

        x_field = semantic.dimension_mappings[0].alias if semantic.dimension_mappings else None
        series_field = next(
            (
                column
                for column in execution.columns
                if column == "comparison_series" or column.endswith("_series") or column == "series"
            ),
            None,
        )

        return ChartSpec(
            chart_type=chart_type,
            title=self._build_title(intent, semantic),
            encoding=ChartEncoding(
                x_field=x_field,
                y_field=semantic.metric_alias,
                series_field=series_field,
            ),
            options={
                "rowCount": execution.row_count,
                "supportsStack": chart_type in {"bar", "line"} and series_field is not None,
            },
        )

    def _is_distribution_query(self, intent: IntentPayload) -> bool:
        keywords = ("распределен", "distribution", "долю", "доля", "breakdown", "proportion")
        raw = (intent.raw_prompt or "").lower()
        return any(kw in raw for kw in keywords)

    def _is_temporal_query(self, intent: IntentPayload) -> bool:
        keywords = ("по годам", "по месяцам", "по неделям", "по дням", "динамик", "менялся", "менялос", "со временем", "trend", "over time")
        raw = (intent.raw_prompt or "").lower()
        return any(kw in raw for kw in keywords)

    def _build_title(self, intent: IntentPayload, semantic: SemanticMappingPayload) -> str:
        metric_label = {
            "revenue": "Revenue",
            "order_count": "Orders",
            "avg_order_value": "Average Order Value",
        }.get(intent.metric or "", "Metric")
        if semantic.dimension_mappings:
            first_dimension = semantic.dimension_mappings[0].label.lower()
            return f"{metric_label} by {first_dimension}"
        return metric_label
