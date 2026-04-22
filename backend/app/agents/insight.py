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

        comparison_series = self._detect_series_column(execution)
        if comparison_series is not None:
            totals = defaultdict(float)
            for row in execution.rows:
                totals[str(row.get(comparison_series))] += float(row.get(metric_alias) or 0)

            labels = list(totals.keys())
            if len(labels) >= 2:
                current_label = self._preferred_current_label(labels)
                comparison_label = next((label for label in labels if label != current_label), labels[1])
                current_total = totals.get(current_label, 0.0)
                comparison_total = totals.get(comparison_label, 0.0)
                if comparison_total == 0:
                    return f"За текущий период показатель составил {self._fmt(current_total)}."
                delta = ((current_total - comparison_total) / comparison_total) * 100
                trend = "выше" if delta >= 0 else "ниже"
                return (
                    f"Текущий период {trend} сравнительного периода на "
                    f"{self._fmt(abs(delta))}% ({self._fmt(current_total)} против {self._fmt(comparison_total)})."
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

    def _detect_series_column(self, execution: QueryExecutionResult) -> str | None:
        preferred = next(
            (
                column
                for column in execution.columns
                if column == "comparison_series" or column.endswith("_series") or column == "series"
            ),
            None,
        )
        if preferred is not None:
            return preferred

        for column in execution.columns:
            values = [row.get(column) for row in execution.rows if row.get(column) is not None]
            distinct = list(dict.fromkeys(str(value) for value in values))
            if 2 <= len(distinct) <= 6:
                return column
        return None

    def _preferred_current_label(self, labels: list[str]) -> str:
        for candidate in ("current_period", "current", "this_period", "actual"):
            if candidate in labels:
                return candidate
        return labels[0]

    def _fmt(self, value: float | int | Any) -> str:
        if isinstance(value, (float, int)):
            if abs(float(value)) >= 1000:
                return f"{float(value):,.2f}".replace(",", " ")
            return f"{float(value):.2f}"
        return str(value)
