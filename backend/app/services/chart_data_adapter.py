from __future__ import annotations

from typing import Any

from app.schemas.query import QueryExecutionResult
from app.services.chart_decision_service import ChartDecision, ResultShape


class ChartDataAdapter:
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
            "ruleId": decision.rule_id,
            "confidence": decision.confidence,
        }

        if decision.chart_type == "metric_card":
            payload.update(self._build_metric_payload(execution, decision, resolved_shape))
            return payload

        x_field = decision.encoding.x_field
        y_field = decision.encoding.y_field
        series_field = decision.encoding.series_field

        if decision.chart_type == "pie":
            payload["slices"] = self._build_pie_slices(execution, x_field, y_field)
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
        x_values = [self._coerce_value(row.get(x_field)) for row in execution.rows] if x_field else []
        y_values = [self._coerce_number(row.get(y_field)) for row in execution.rows] if y_field else []
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
        x_values = self._ordered_unique([self._coerce_value(row.get(x_field)) for row in execution.rows]) if x_field else []
        groups = self._ordered_unique([self._coerce_value(row.get(series_field)) for row in execution.rows]) if series_field else []
        series = []
        for group in groups:
            series.append(
                {
                    "name": group,
                    "data": [
                        self._sum_matching_rows(execution.rows, x_field, series_field, x_value, group, y_field)
                        for x_value in x_values
                    ],
                }
            )
        return {
            "x": {
                "field": x_field,
                "values": x_values,
                "type": self._infer_axis_type(x_field, execution.rows),
            },
            "series": series,
            "seriesField": series_field,
            "stackable": decision.variant == "stacked",
            "stacked": decision.variant == "stacked",
        }

    def _build_pie_slices(
        self,
        execution: QueryExecutionResult,
        x_field: str | None,
        y_field: str | None,
    ) -> list[dict[str, Any]]:
        slices: list[dict[str, Any]] = []
        for index, row in enumerate(execution.rows):
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

    def _sum_matching_rows(
        self,
        rows: list[dict[str, Any]],
        x_field: str | None,
        series_field: str | None,
        x_value: Any,
        series_value: Any,
        y_field: str | None,
    ) -> float:
        total = 0.0
        for row in rows:
            if x_field is not None and self._coerce_value(row.get(x_field)) != x_value:
                continue
            if series_field is not None and self._coerce_value(row.get(series_field)) != series_value:
                continue
            total += self._coerce_number(row.get(y_field))
        return total

    def _ordered_unique(self, values: list[Any]) -> list[Any]:
        seen: set[str] = set()
        ordered: list[Any] = []
        for value in values:
            key = repr(value)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(value)
        return ordered

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
