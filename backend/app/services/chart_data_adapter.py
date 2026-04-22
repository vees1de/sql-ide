from __future__ import annotations

from typing import Any

from app.schemas.query import QueryExecutionResult
from app.services.chart_decision_service import ChartDecision, ResultShape


class ChartDataAdapter:
    OTHER_LABEL = "Other"

    def build(
        self,
        execution: QueryExecutionResult,
        decision: ChartDecision,
        shape: ResultShape | None = None,
    ) -> dict[str, Any]:
        resolved_shape = shape
        if resolved_shape is None:
            from app.services.chart_decision_service import ResultShapeAnalyzer

            resolved_shape = ResultShapeAnalyzer().analyze(execution)

        payload: dict[str, Any] = {
            "kind": self._payload_kind(decision.chart_type, bool(decision.encoding.series_field), decision.variant),
            "chartType": decision.chart_type,
            "variant": decision.variant,
            "explanation": decision.explanation,
            "reason": decision.reason,
            "ruleId": decision.rule_id,
            "confidence": decision.confidence,
            "semanticIntent": decision.semantic_intent,
            "analysisMode": decision.analysis_mode,
            "visualGoal": decision.visual_goal,
            "timeRole": decision.time_role,
            "comparisonGoal": decision.comparison_goal,
            "preferredMark": decision.preferred_mark,
            "alternatives": list(decision.alternatives),
            "candidates": [candidate.model_dump(mode="json") for candidate in decision.candidates],
            "constraintsApplied": list(decision.constraints_applied),
            "visualLoad": decision.visual_load,
            "reasonCodes": list(decision.reason_codes),
            "queryInterpretation": decision.query_interpretation.model_dump(mode="json") if decision.query_interpretation else None,
            "decisionSummary": decision.decision_summary.model_dump(mode="json") if decision.decision_summary else None,
            "understanding": decision.query_interpretation.model_dump(mode="json") if decision.query_interpretation else None,
            "decision": {
                "chart_type": decision.decision_summary.selected_chart if decision.decision_summary else decision.chart_type,
                "x": decision.encoding.x_field,
                "y": decision.encoding.y_field,
                "series_key": decision.encoding.series_field,
                "facet_key": decision.encoding.facet_field,
                "normalize": decision.encoding.normalize,
                "series_limit": decision.encoding.series_limit,
                "category_limit": decision.encoding.category_limit,
                "top_n_strategy": decision.encoding.top_n_strategy,
            },
            "explanationBlock": {
                "summary": decision.reason,
                "confidence": decision.confidence,
                "alternatives_considered": list(decision.alternatives),
                "reason_codes": list(decision.reason_codes),
            },
            "config": {
                "xField": decision.encoding.x_field,
                "yField": decision.encoding.y_field,
                "seriesField": decision.encoding.series_field,
                "facetField": decision.encoding.facet_field,
                "sort": decision.encoding.sort,
                "normalize": decision.encoding.normalize,
                "seriesLimit": decision.encoding.series_limit,
                "categoryLimit": decision.encoding.category_limit,
                "topNStrategy": decision.encoding.top_n_strategy,
                "valueFormat": decision.encoding.value_format,
                "dataRoles": decision.encoding.data_roles.model_dump(mode="json") if decision.encoding.data_roles else None,
            },
        }

        if decision.chart_type == "table":
            return payload

        if decision.chart_type == "metric_card":
            payload.update(self._build_metric_payload(execution, decision, resolved_shape))
            return payload

        x_field = decision.encoding.x_field
        y_field = decision.encoding.y_field
        series_field = decision.encoding.series_field

        if decision.chart_type == "pie":
            payload["slices"] = self._build_pie_slices(execution, x_field, y_field, decision)
            return payload

        if series_field:
            payload.update(self._build_multi_series_payload(execution, x_field, y_field, series_field, decision))
            return payload

        payload.update(self._build_single_series_payload(execution, x_field, y_field, decision))
        return payload

    def _payload_kind(self, chart_type: str, has_series: bool, variant: str | None) -> str:
        if chart_type == "metric_card":
            return "kpi"
        if chart_type == "pie":
            return "pie"
        if chart_type in {"line", "bar"} and (has_series or variant in {"multi_series", "grouped", "stacked"}):
            return "multi_series"
        if chart_type in {"line", "bar"}:
            return "single_series"
        return "table"

    def _build_single_series_payload(
        self,
        execution: QueryExecutionResult,
        x_field: str | None,
        y_field: str | None,
        decision: ChartDecision,
    ) -> dict[str, Any]:
        prepared = self._prepare_single_series_rows(execution.rows, x_field, y_field, decision)
        x_values = [self._coerce_value(row.get(x_field)) for row in prepared] if x_field else []
        y_values = [self._coerce_number(row.get(y_field)) for row in prepared] if y_field else []
        return {
            "x": {
                "field": x_field,
                "values": x_values,
                "type": self._infer_axis_type(x_field, execution.rows),
            },
            "y": {
                "field": y_field,
                "values": y_values,
                "unit": None,
            },
            "stacked": decision.variant == "stacked",
        }

    def _build_multi_series_payload(
        self,
        execution: QueryExecutionResult,
        x_field: str | None,
        y_field: str | None,
        series_field: str | None,
        decision: ChartDecision,
    ) -> dict[str, Any]:
        x_values, groups, matrix = self._prepare_multi_series_matrix(execution.rows, x_field, y_field, series_field, decision)
        series = [
            {
                "name": group,
                "data": [matrix.get((x_value, group), 0.0) for x_value in x_values],
            }
            for group in groups
        ]
        return {
            "x": {
                "field": x_field,
                "values": x_values,
                "type": self._infer_axis_type(x_field, execution.rows),
            },
            "series": series,
            "seriesField": series_field,
            "facetField": decision.encoding.facet_field,
            "stackable": decision.variant == "stacked",
            "stacked": decision.variant == "stacked",
        }

    def _build_pie_slices(
        self,
        execution: QueryExecutionResult,
        x_field: str | None,
        y_field: str | None,
        decision: ChartDecision,
    ) -> list[dict[str, Any]]:
        rows = self._prepare_single_series_rows(execution.rows, x_field, y_field, decision)
        slices: list[dict[str, Any]] = []
        for index, row in enumerate(rows):
            slices.append(
                {
                    "name": self._coerce_value(row.get(x_field)) if x_field else f"Segment {index + 1}",
                    "value": self._coerce_number(row.get(y_field)),
                }
            )
        return slices

    def _build_metric_payload(
        self,
        execution: QueryExecutionResult,
        decision: ChartDecision,
        shape: ResultShape,
    ) -> dict[str, Any]:
        field = decision.encoding.y_field or (shape.numeric_columns[0].name if shape.numeric_columns else None)
        value: float | int | str | None = None
        if field and execution.rows:
            value = self._coerce_number(execution.rows[0].get(field))
        if value is None:
            value = self._first_numeric(execution.rows)
        return {
            "value": value if value is not None else 0,
            "metricLabel": field,
        }

    def _prepare_single_series_rows(
        self,
        rows: list[dict[str, Any]],
        x_field: str | None,
        y_field: str | None,
        decision: ChartDecision,
    ) -> list[dict[str, Any]]:
        if not x_field or not y_field:
            return list(rows)
        aggregated = self._aggregate_single_series_rows(rows, x_field, y_field)
        sorted_rows = self._sort_rows(aggregated, x_field, y_field, decision.encoding.sort, axis_is_temporal=self._field_is_temporal(x_field, rows))
        limit = decision.encoding.category_limit
        if limit and not self._field_is_temporal(x_field, rows):
            sorted_rows = self._apply_single_dimension_limit(sorted_rows, x_field, y_field, limit, decision.encoding.top_n_strategy)
        return sorted_rows

    def _prepare_multi_series_matrix(
        self,
        rows: list[dict[str, Any]],
        x_field: str | None,
        y_field: str | None,
        series_field: str | None,
        decision: ChartDecision,
    ) -> tuple[list[Any], list[Any], dict[tuple[Any, Any], float]]:
        if not x_field or not y_field or not series_field:
            return [], [], {}

        matrix: dict[tuple[Any, Any], float] = {}
        totals_by_x: dict[Any, float] = {}
        totals_by_group: dict[Any, float] = {}

        for row in rows:
            x_value = self._coerce_value(row.get(x_field))
            group = self._coerce_value(row.get(series_field))
            value = self._coerce_number(row.get(y_field))
            key = (x_value, group)
            matrix[key] = matrix.get(key, 0.0) + value
            totals_by_x[x_value] = totals_by_x.get(x_value, 0.0) + value
            totals_by_group[group] = totals_by_group.get(group, 0.0) + value

        series_limit = decision.encoding.series_limit
        kept_groups, groups_have_other = self._resolve_top_values(
            totals_by_group,
            series_limit,
            decision.encoding.top_n_strategy,
        )
        category_limit = decision.encoding.category_limit if not self._field_is_temporal(x_field, rows) else None
        kept_x, x_have_other = self._resolve_top_values(
            totals_by_x,
            category_limit,
            decision.encoding.top_n_strategy,
        )

        collapsed: dict[tuple[Any, Any], float] = {}
        for (x_value, group), value in matrix.items():
            normalized_x = self._collapse_value(x_value, kept_x, x_have_other)
            normalized_group = self._collapse_value(group, kept_groups, groups_have_other)
            if normalized_x is None or normalized_group is None:
                continue
            collapsed[(normalized_x, normalized_group)] = collapsed.get((normalized_x, normalized_group), 0.0) + value

        resolved_x_totals: dict[Any, float] = {}
        resolved_group_totals: dict[Any, float] = {}
        for (x_value, group), value in collapsed.items():
            resolved_x_totals[x_value] = resolved_x_totals.get(x_value, 0.0) + value
            resolved_group_totals[group] = resolved_group_totals.get(group, 0.0) + value

        x_values = self._sort_dimension_values(
            list(resolved_x_totals.keys()),
            resolved_x_totals,
            decision.encoding.sort,
            axis_is_temporal=self._field_is_temporal(x_field, rows),
        )
        groups = self._sort_dimension_values(
            list(resolved_group_totals.keys()),
            resolved_group_totals,
            "value_desc",
            axis_is_temporal=False,
        )
        return x_values, groups, collapsed

    def _aggregate_single_series_rows(
        self,
        rows: list[dict[str, Any]],
        x_field: str,
        y_field: str,
    ) -> list[dict[str, Any]]:
        aggregated: dict[Any, float] = {}
        for row in rows:
            x_value = self._coerce_value(row.get(x_field))
            aggregated[x_value] = aggregated.get(x_value, 0.0) + self._coerce_number(row.get(y_field))
        return [{x_field: key, y_field: value} for key, value in aggregated.items()]

    def _apply_single_dimension_limit(
        self,
        rows: list[dict[str, Any]],
        x_field: str,
        y_field: str,
        limit: int,
        strategy: str | None,
    ) -> list[dict[str, Any]]:
        if len(rows) <= limit or limit <= 0:
            return rows
        if strategy != "top_plus_other" or limit == 1:
            return rows[:limit]
        kept = rows[: limit - 1]
        other_total = sum(self._coerce_number(row.get(y_field)) for row in rows[limit - 1 :])
        kept.append({x_field: self.OTHER_LABEL, y_field: other_total})
        return kept

    def _resolve_top_values(
        self,
        totals: dict[Any, float],
        limit: int | None,
        strategy: str | None,
    ) -> tuple[set[Any], bool]:
        if not limit or len(totals) <= limit:
            return set(totals.keys()), False
        ordered = [name for name, _value in sorted(totals.items(), key=lambda item: item[1], reverse=True)]
        if strategy == "top_plus_other" and limit > 1:
            return set(ordered[: limit - 1]), True
        return set(ordered[:limit]), False

    def _collapse_value(self, value: Any, kept: set[Any], include_other: bool) -> Any | None:
        if value in kept:
            return value
        if include_other:
            return self.OTHER_LABEL
        return None

    def _sort_rows(
        self,
        rows: list[dict[str, Any]],
        x_field: str,
        y_field: str,
        sort: str | None,
        *,
        axis_is_temporal: bool,
    ) -> list[dict[str, Any]]:
        if sort == "value_desc":
            return sorted(rows, key=lambda row: self._coerce_number(row.get(y_field)), reverse=True)
        if sort == "time_asc" or axis_is_temporal:
            return sorted(rows, key=lambda row: self._sortable_value(row.get(x_field)))
        return rows

    def _sort_dimension_values(
        self,
        values: list[Any],
        totals: dict[Any, float],
        sort: str | None,
        *,
        axis_is_temporal: bool,
    ) -> list[Any]:
        other_present = self.OTHER_LABEL in values
        core_values = [value for value in values if value != self.OTHER_LABEL]
        if sort == "value_desc":
            core_values = sorted(core_values, key=lambda value: totals.get(value, 0.0), reverse=True)
        elif sort == "time_asc" or axis_is_temporal:
            core_values = sorted(core_values, key=self._sortable_value)
        if other_present:
            core_values.append(self.OTHER_LABEL)
        return core_values

    def _field_is_temporal(self, field: str | None, rows: list[dict[str, Any]]) -> bool:
        return self._infer_axis_type(field, rows) == "temporal"

    def _infer_axis_type(self, field: str | None, rows: list[dict[str, Any]]) -> str | None:
        if field is None:
            return None
        lowered = field.lower()
        if any(token in lowered for token in ("date", "time", "day", "week", "month", "year")):
            return "temporal"
        if rows:
            sample = rows[0].get(field)
            if isinstance(sample, (int, float)):
                return "numeric"
        return "categorical"

    def _sortable_value(self, value: Any) -> Any:
        if value is None:
            return ""
        return str(value)

    def _coerce_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float, bool)):
            return value
        return str(value)

    def _coerce_number(self, value: Any) -> float:
        if isinstance(value, bool) or value is None:
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(str(value).replace(",", "."))
        except Exception:
            return 0.0

    def _first_numeric(self, rows: list[dict[str, Any]]) -> float | None:
        for row in rows:
            for value in row.values():
                number = self._coerce_number(value)
                if number != 0.0 or value in {0, 0.0, "0", "0.0"}:
                    return number
        return None
