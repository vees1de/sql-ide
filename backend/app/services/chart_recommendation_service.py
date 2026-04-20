from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date, datetime
from typing import Any

from app.schemas.chat import ChartRecommendation


class ChartRecommendationService:
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

    def recommend(
        self,
        columns: list[dict[str, Any]],
        rows_preview: list[dict[str, Any]],
        row_count: int,
    ) -> ChartRecommendation:
        if not columns or row_count <= 1 or len(columns) > 8:
            return self._table("Недостаточно данных для надёжной визуализации.")

        analysed = [self._analyse_column(column, rows_preview) for column in columns]
        numeric = [item for item in analysed if item["is_numeric"]]
        temporal = [item for item in analysed if item["is_temporal"]]
        categorical = [item for item in analysed if not item["is_numeric"] and not item["is_temporal"]]

        if row_count > 500:
            return self._table("Слишком много строк для компактного графика.")

        if len(numeric) == 1 and temporal and len(columns) <= 4:
            x = temporal[0]["name"]
            y = numeric[0]["name"]
            return ChartRecommendation(
                recommended_view="chart",
                chart_type="line",
                x=x,
                y=y,
                reason="Одна временная ось и одна числовая метрика подходят для линейного графика.",
            )

        if len(numeric) == 1 and categorical and row_count <= 30:
            x = categorical[0]["name"]
            y = numeric[0]["name"]
            distinct = categorical[0]["distinct_count"]
            if distinct <= 6 and self._looks_like_percentage(rows_preview, y, x):
                return ChartRecommendation(
                    recommended_view="chart",
                    chart_type="pie",
                    x=x,
                    y=y,
                    reason="Доли близки к 100% и категорий немного, поэтому уместна круговая диаграмма.",
                )
            return ChartRecommendation(
                recommended_view="chart",
                chart_type="bar",
                x=x,
                y=y,
                reason="Одна категория и одна метрика при небольшом числе строк хорошо читаются в столбчатом графике.",
            )

        if len(numeric) >= 1 and len(categorical) >= 1:
            series_candidate = next((item for item in categorical if item["distinct_count"] <= 5), None)
            if series_candidate and len(categorical) >= 2:
                x_candidate = next(
                    (item for item in analysed if item is not series_candidate and not item["is_numeric"]),
                    categorical[0],
                )
                y = numeric[0]["name"]
                return ChartRecommendation(
                    recommended_view="chart",
                    chart_type="stacked_bar",
                    x=x_candidate["name"],
                    y=y,
                    series=series_candidate["name"],
                    reason="Небольшое число серий и числовая метрика хорошо читаются в накопленной столбчатой диаграмме.",
                )

        if len(categorical) >= 1 and len(numeric) >= 1:
            first_numeric = numeric[0]
            first_category = categorical[0]
            if first_category["distinct_count"] <= 6 and self._looks_like_percentage(rows_preview, first_numeric["name"], first_category["name"]):
                return ChartRecommendation(
                    recommended_view="chart",
                    chart_type="pie",
                    x=first_category["name"],
                    y=first_numeric["name"],
                    reason="Доли суммируются примерно до 100%, поэтому круговая диаграмма будет понятнее таблицы.",
                )

        return self._table("Набор данных лучше читается в табличном виде.")

    def _analyse_column(self, column: dict[str, Any], rows_preview: list[dict[str, Any]]) -> dict[str, Any]:
        name = str(column.get("name") or "").strip()
        type_name = str(column.get("type") or "").strip().lower()
        values = [row.get(name) for row in rows_preview if row.get(name) is not None]
        distinct_count = len({self._normalize_value(value) for value in values if self._normalize_value(value) is not None})
        is_numeric = self._looks_numeric_type(type_name) or self._looks_numeric_values(values)
        is_temporal = self._looks_temporal_type(type_name) or self._looks_temporal_name(name) or self._looks_temporal_values(values)
        return {
            "name": name,
            "type": type_name,
            "values": values,
            "distinct_count": distinct_count,
            "is_numeric": is_numeric,
            "is_temporal": is_temporal and not is_numeric,
        }

    def _looks_numeric_type(self, type_name: str) -> bool:
        return any(hint in type_name for hint in self.NUMERIC_TYPE_HINTS)

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

    def _looks_temporal_type(self, type_name: str) -> bool:
        return "date" in type_name or "time" in type_name or "timestamp" in type_name

    def _looks_temporal_name(self, name: str) -> bool:
        lowered = name.lower()
        return any(hint in lowered for hint in self.TEMPORAL_NAME_HINTS)

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

    def _looks_like_percentage(self, rows_preview: list[dict[str, Any]], y_name: str, x_name: str) -> bool:
        if not rows_preview:
            return False
        values: list[float] = []
        for row in rows_preview:
            raw_value = row.get(y_name)
            if raw_value is None:
                return False
            try:
                values.append(float(str(raw_value).replace(",", ".")))
            except Exception:
                return False
        total = sum(values)
        if total <= 0:
            return False
        categories = {str(row.get(x_name)) for row in rows_preview if row.get(x_name) is not None}
        return len(categories) <= 6 and 95 <= total <= 105

    def _normalize_value(self, value: Any) -> Any:
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, float):
            return round(value, 6)
        if isinstance(value, int):
            return value
        text = str(value).strip()
        return text or None

    def _table(self, reason: str) -> ChartRecommendation:
        return ChartRecommendation(recommended_view="table", chart_type=None, reason=reason)
