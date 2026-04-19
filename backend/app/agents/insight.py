from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.schemas.query import IntentPayload, QueryExecutionResult, SemanticMappingPayload


class InsightAgent:
    def run(
        self,
        intent: IntentPayload,
        semantic: SemanticMappingPayload,
        execution: QueryExecutionResult,
    ) -> str:
        metric_alias = semantic.metric_alias or self._detect_metric_column(execution.columns)
        if metric_alias is None or not execution.rows:
            return "Запрос выполнен, но данных для текстового вывода недостаточно."

        if "period_label" in execution.columns:
            totals = defaultdict(float)
            for row in execution.rows:
                totals[str(row.get("period_label"))] += float(row.get(metric_alias) or 0)
            current_total = totals.get("current_period", 0.0)
            previous_total = totals.get("previous_year", 0.0)
            if previous_total == 0:
                return f"За текущий период показатель составил {self._fmt(current_total)}."
            delta = ((current_total - previous_total) / previous_total) * 100
            trend = "выше" if delta >= 0 else "ниже"
            return (
                f"Текущий период {trend} аналогичного периода прошлого года на "
                f"{self._fmt(abs(delta))}% ({self._fmt(current_total)} против {self._fmt(previous_total)})."
            )

        if not semantic.dimension_mappings:
            value = float(execution.rows[0].get(metric_alias) or 0)
            return f"По выбранным условиям показатель составил {self._fmt(value)}."

        first_dimension = semantic.dimension_mappings[0].alias
        series = [
            (str(row.get(first_dimension)), float(row.get(metric_alias) or 0))
            for row in execution.rows
            if row.get(metric_alias) is not None
        ]
        if not series:
            return "Данные получены, но в них нет значений для построения краткого вывода."

        if semantic.dimension_mappings[0].key in {"day", "week", "month"} and len(series) >= 2:
            first_value = series[0][1]
            last_label, last_value = series[-1]
            if first_value == 0:
                return f"Последняя точка {last_label} дала значение {self._fmt(last_value)}."
            delta = ((last_value - first_value) / first_value) * 100
            direction = "вырос" if delta >= 0 else "снизился"
            return f"Показатель {direction} на {self._fmt(abs(delta))}% и достиг {self._fmt(last_value)} в точке {last_label}."

        leader_label, leader_value = max(series, key=lambda item: item[1])
        return f"Лидирующая категория: {leader_label} со значением {self._fmt(leader_value)}."

    def _detect_metric_column(self, columns: list[str]) -> str | None:
        for column in columns:
            if column.startswith("total_") or column.endswith("_value"):
                return column
        return None

    def _fmt(self, value: float | int | Any) -> str:
        if isinstance(value, (float, int)):
            if abs(float(value)) >= 1000:
                return f"{float(value):,.2f}".replace(",", " ")
            return f"{float(value):.2f}"
        return str(value)
