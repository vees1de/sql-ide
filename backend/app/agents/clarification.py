from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.schemas.metadata import ColumnMetadata, SchemaMetadataResponse
from app.schemas.query import IntentPayload

_METRIC_NAME_HINTS = (
    "amount",
    "revenue",
    "total",
    "price",
    "sum",
    "count",
    "qty",
    "quantity",
    "sales",
    "value",
    "cost",
    "fee",
    "order",
)


@dataclass
class ClarificationOptionData:
    id: str
    label: str
    detail: str | None = None
    reason: str | None = None


@dataclass
class ClarificationBlockData:
    clarification_id: str
    question: str
    ambiguity_type: str
    answer_type: str
    options: list[ClarificationOptionData]
    recommended_option_id: str | None = None


class ClarificationAgent:
    """Builds structured clarification payload with stable option IDs of the form ``{ambiguity}:{value}``."""

    def run(
        self,
        intent: IntentPayload,
        schema: SchemaMetadataResponse | None = None,
    ) -> ClarificationBlockData:
        ambiguity_type, options = self._build_options(intent, schema)

        question = intent.clarification_question or self._default_question(ambiguity_type)
        if not options:
            options = [
                ClarificationOptionData(
                    id=f"{ambiguity_type}:free_text",
                    label="Уточнить в следующем сообщении",
                    detail="Опишите метрику, таблицу или период свободным текстом.",
                )
            ]

        return ClarificationBlockData(
            clarification_id=str(uuid.uuid4()),
            question=question,
            ambiguity_type=ambiguity_type,
            answer_type="single_select",
            options=options,
            recommended_option_id=options[0].id if options else None,
        )

    # ------------------------------------------------------------------
    def _build_options(
        self,
        intent: IntentPayload,
        schema: SchemaMetadataResponse | None,
    ) -> tuple[str, list[ClarificationOptionData]]:
        ambiguities = [a.lower() for a in intent.ambiguities]

        if "sales" in ambiguities or intent.metric is None:
            return "metric", self._metric_options(schema)

        if not intent.dimensions and any("dimension" in a for a in ambiguities):
            return "dimension", self._dimension_options(schema)

        if intent.date_range is None and any("time" in a or "period" in a for a in ambiguities):
            return "time_range", self._time_options()

        # Default — treat as metric ambiguity when we have no better signal.
        return "other", self._metric_options(schema)

    def _metric_options(self, schema: SchemaMetadataResponse | None) -> list[ClarificationOptionData]:
        options: list[ClarificationOptionData] = [
            ClarificationOptionData(id="metric:revenue", label="Выручка", detail="Сумма продаж"),
            ClarificationOptionData(id="metric:order_count", label="Количество заказов"),
            ClarificationOptionData(id="metric:avg_order_value", label="Средний чек"),
        ]
        if schema and schema.tables:
            extra = self._metric_options_from_schema(schema)
            known_ids = {opt.id for opt in options}
            for opt in extra:
                if opt.id not in known_ids:
                    options.append(opt)
                    known_ids.add(opt.id)
                if len(options) >= 6:
                    break
        return options

    def _metric_options_from_schema(
        self, schema: SchemaMetadataResponse
    ) -> list[ClarificationOptionData]:
        results: list[ClarificationOptionData] = []
        for table in schema.tables:
            metric_cols = [c.name for c in table.columns if self._looks_like_metric_column(c)][:4]
            if not metric_cols:
                continue
            for col in metric_cols:
                option_id = f"metric:{table.name}.{col}"
                label = f"{table.name}.{col}"
                results.append(
                    ClarificationOptionData(
                        id=option_id,
                        label=label,
                        detail=f"Колонка таблицы «{table.name}»",
                    )
                )
                if len(results) >= 6:
                    return results
        return results

    def _dimension_options(self, schema: SchemaMetadataResponse | None) -> list[ClarificationOptionData]:
        base = [
            ClarificationOptionData(id="dimension:month", label="По месяцам"),
            ClarificationOptionData(id="dimension:week", label="По неделям"),
            ClarificationOptionData(id="dimension:day", label="По дням"),
        ]
        if schema and schema.tables:
            for table in schema.tables[:4]:
                for col in table.columns[:3]:
                    if "id" in col.name.lower():
                        continue
                    if self._looks_like_metric_column(col):
                        continue
                    base.append(
                        ClarificationOptionData(
                            id=f"dimension:{table.name}.{col.name}",
                            label=f"{table.name}.{col.name}",
                            detail="Колонка для группировки",
                        )
                    )
        return base[:6]

    def _time_options(self) -> list[ClarificationOptionData]:
        return [
            ClarificationOptionData(id="time_range:last_30d", label="Последние 30 дней"),
            ClarificationOptionData(id="time_range:last_90d", label="Последние 90 дней"),
            ClarificationOptionData(id="time_range:ytd", label="С начала года"),
            ClarificationOptionData(id="time_range:all", label="Без фильтра по времени"),
        ]

    @staticmethod
    def _default_question(ambiguity_type: str) -> str:
        if ambiguity_type == "metric":
            return "Какую метрику имеете в виду?"
        if ambiguity_type == "dimension":
            return "По какому измерению сгруппировать?"
        if ambiguity_type == "time_range":
            return "За какой период показать данные?"
        return "Уточните, что именно показать."

    @staticmethod
    def _looks_like_metric_column(column: ColumnMetadata) -> bool:
        type_lower = column.type.lower()
        if any(x in type_lower for x in ("int", "numeric", "decimal", "float", "double", "real", "money")):
            return True
        name_lower = column.name.lower()
        return any(h in name_lower for h in _METRIC_NAME_HINTS)
