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

# Keywords per ambiguity type — checked against lowercased ambiguity strings
_DATE_KEYWORDS   = ("date", "time", "period", "range", "year", "month", "interval", "дата", "период", "год", "месяц", "диапазон", "время")
_LIMIT_KEYWORDS  = ("количество", "сколько", "limit", "top", "топ", "число", "записей", "строк", "команд", "игроков", "результатов", "показать")
_METRIC_KEYWORDS = ("metric", "метрика", "показатель", "measure", "sales", "what", "какую")
_DIM_KEYWORDS    = ("dimension", "измерение", "группировка", "group", "segment", "breakdown")


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
        # 1. Prefer LLM-generated options when available — the LLM knows the actual context
        llm_options = getattr(intent, "clarification_options", None) or []
        if llm_options:
            options = [
                ClarificationOptionData(
                    id=opt.id,
                    label=opt.label,
                    detail=opt.detail,
                    reason=opt.reason,
                )
                for opt in llm_options
            ]
            ambiguity_type = self._infer_ambiguity_type_from_options(options, intent)
            question = intent.clarification_question or self._default_question(ambiguity_type)
            return ClarificationBlockData(
                clarification_id=str(uuid.uuid4()),
                question=question,
                ambiguity_type=ambiguity_type,
                answer_type="single_select",
                options=options,
                recommended_option_id=options[0].id if options else None,
            )

        # 2. Fallback to rule-based classification when LLM did not provide options
        ambiguity_type, options = self._build_options(intent, schema)

        question = intent.clarification_question or self._default_question(ambiguity_type)
        if not options:
            options = [
                ClarificationOptionData(
                    id=f"{ambiguity_type}:free_text",
                    label="Уточнить в следующем сообщении",
                    detail="Опишите деталь свободным текстом.",
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

    @staticmethod
    def _infer_ambiguity_type_from_options(
        options: list[ClarificationOptionData], intent: IntentPayload
    ) -> str:
        """Infer ambiguity type from LLM-provided option ids when they follow a prefix convention."""
        ids_lower = [(o.id or "").lower() for o in options]
        if any(i.startswith(("limit", "top")) for i in ids_lower):
            return "limit"
        if any(i.startswith(("time", "date", "year", "period")) for i in ids_lower):
            return "time_range"
        if any(i.startswith("metric") for i in ids_lower):
            return "metric"
        if any(i.startswith("dim") for i in ids_lower):
            return "dimension"
        if any(i.startswith("join") for i in ids_lower):
            return "join_path"
        return "other"

    # ------------------------------------------------------------------
    def _build_options(
        self,
        intent: IntentPayload,
        schema: SchemaMetadataResponse | None,
    ) -> tuple[str, list[ClarificationOptionData]]:
        ambiguities = [a.lower() for a in (intent.ambiguities or [])]
        ambiguity_text = " ".join(ambiguities)

        def matches(keywords: tuple[str, ...]) -> bool:
            return any(kw in ambiguity_text for kw in keywords)

        # 1. Limit / count ambiguity ("сколько команд?", "top N")
        if matches(_LIMIT_KEYWORDS):
            return "limit", self._limit_options()

        # 2. Date / time ambiguity ("date_range", "период", "год")
        if intent.date_range is None and matches(_DATE_KEYWORDS):
            return "time_range", self._time_options(schema)

        # 3. Metric ambiguity
        if intent.metric is None or matches(_METRIC_KEYWORDS):
            return "metric", self._metric_options(schema)

        # 4. Dimension ambiguity
        if not intent.dimensions and matches(_DIM_KEYWORDS):
            return "dimension", self._dimension_options(schema)

        # 5. Default: if date is missing try time, otherwise infer from schema
        if intent.date_range is None and self._schema_has_date_column(schema):
            return "time_range", self._time_options(schema)

        schema_opts = self._metric_options_from_schema(schema)
        return "other", schema_opts[:6] if schema_opts else self._limit_options()

    # ------------------------------------------------------------------
    # Option builders
    # ------------------------------------------------------------------

    @staticmethod
    def _limit_options() -> list[ClarificationOptionData]:
        return [
            ClarificationOptionData(id="limit:5",   label="Топ 5",  detail="Первые 5 записей"),
            ClarificationOptionData(id="limit:10",  label="Топ 10", detail="Первые 10 записей", reason="Рекомендуется"),
            ClarificationOptionData(id="limit:20",  label="Топ 20", detail="Первые 20 записей"),
            ClarificationOptionData(id="limit:50",  label="Топ 50", detail="Первые 50 записей"),
            ClarificationOptionData(id="limit:all", label="Все",    detail="Без ограничения по количеству"),
        ]

    def _metric_options(self, schema: SchemaMetadataResponse | None) -> list[ClarificationOptionData]:
        schema_options = self._metric_options_from_schema(schema)
        if len(schema_options) >= 3:
            return schema_options[:5]
        if schema_options:
            fallback_options = self._metric_fallback_options()
            combined: list[ClarificationOptionData] = []
            seen_labels: set[str] = set()
            for option in [*schema_options, *fallback_options]:
                label_key = option.label.lower()
                if label_key in seen_labels:
                    continue
                combined.append(option)
                seen_labels.add(label_key)
                if len(combined) >= 5:
                    return combined
            return combined
        # Fallback only when schema unavailable. Keep the options concrete enough to
        # cover the common "quality of rides" ambiguity without inventing schema terms.
        return self._metric_fallback_options()

    @staticmethod
    def _metric_fallback_options() -> list[ClarificationOptionData]:
        return [
            ClarificationOptionData(
                id="metric:completion_rate",
                label="Коэффициент завершённости",
                detail="Доля завершённых поездок",
            ),
            ClarificationOptionData(
                id="metric:avg_duration",
                label="Средняя длительность поездки",
                detail="Среднее время в пути",
            ),
            ClarificationOptionData(
                id="metric:distance",
                label="Средняя дистанция",
                detail="Средняя длина поездки",
            ),
            ClarificationOptionData(
                id="metric:cancellation_rate",
                label="Коэффициент отмены",
                detail="Доля отменённых поездок",
            ),
            ClarificationOptionData(
                id="metric:arrival_time",
                label="Среднее время прибытия водителя",
                detail="Среднее время до прибытия",
            ),
        ]

    def _metric_options_from_schema(
        self, schema: SchemaMetadataResponse | None
    ) -> list[ClarificationOptionData]:
        if not schema:
            return []
        results: list[ClarificationOptionData] = []
        for table in schema.tables:
            metric_cols = [c.name for c in table.columns if self._looks_like_metric_column(c)][:4]
            for col in metric_cols:
                if col.lower().endswith("_id") or col.lower() == "id":
                    continue
                label = self._label_metric_column(col)
                results.append(ClarificationOptionData(
                    id=f"metric:{table.name}.{col}",
                    label=label,
                    detail=f"Колонка таблицы «{table.name}» ({col})" if label != f"{table.name}.{col}" else f"Колонка таблицы «{table.name}»",
                ))
                if len(results) >= 5:
                    return results
        return results

    def _dimension_options(self, schema: SchemaMetadataResponse | None) -> list[ClarificationOptionData]:
        base = [
            ClarificationOptionData(id="dimension:month", label="По месяцам"),
            ClarificationOptionData(id="dimension:week",  label="По неделям"),
            ClarificationOptionData(id="dimension:day",   label="По дням"),
        ]
        if schema and schema.tables:
            for table in schema.tables[:4]:
                for col in table.columns[:3]:
                    if "id" in col.name.lower() or self._looks_like_metric_column(col):
                        continue
                    base.append(ClarificationOptionData(
                        id=f"dimension:{table.name}.{col.name}",
                        label=f"{table.name}.{col.name}",
                        detail="Колонка для группировки",
                    ))
        return base[:6]

    def _time_options(self, schema: SchemaMetadataResponse | None = None) -> list[ClarificationOptionData]:
        if self._schema_has_date_column(schema):
            return [
                ClarificationOptionData(id="time_range:all",       label="Весь период",              detail="Без фильтра по дате"),
                ClarificationOptionData(id="time_range:last_year", label="Последний год в данных"),
                ClarificationOptionData(id="time_range:last_3y",   label="Последние 3 года в данных"),
                ClarificationOptionData(id="time_range:custom",    label="Указать диапазон",         detail="Например: 2013–2015"),
            ]
        return [
            ClarificationOptionData(id="time_range:last_30d", label="Последние 30 дней"),
            ClarificationOptionData(id="time_range:last_90d", label="Последние 90 дней"),
            ClarificationOptionData(id="time_range:ytd",      label="С начала года"),
            ClarificationOptionData(id="time_range:all",      label="Весь период"),
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _schema_has_date_column(schema: SchemaMetadataResponse | None) -> bool:
        if not schema:
            return False
        for table in schema.tables:
            for col in table.columns:
                if any(kw in col.name.lower() for kw in ("date", "year", "time", "period", "season")):
                    return True
                if any(kw in col.type.lower() for kw in ("date", "timestamp", "time")):
                    return True
        return False

    @staticmethod
    def _default_question(ambiguity_type: str) -> str:
        return {
            "metric":     "Какую метрику имеете в виду?",
            "dimension":  "По какому измерению сгруппировать?",
            "time_range": "За какой период показать данные?",
            "limit":      "Сколько записей показать?",
        }.get(ambiguity_type, "Уточните, что именно показать.")

    @staticmethod
    def _looks_like_metric_column(column: ColumnMetadata) -> bool:
        if any(x in column.type.lower() for x in ("int", "numeric", "decimal", "float", "double", "real", "money")):
            return True
        return any(h in column.name.lower() for h in _METRIC_NAME_HINTS)

    @staticmethod
    def _label_metric_column(column_name: str) -> str:
        lowered = column_name.lower()
        pattern_labels = (
            (("completion", "complete", "completed", "done", "status"), "Коэффициент завершённости"),
            (("duration", "time", "minutes", "minute", "mins", "min"), "Средняя длительность поездки"),
            (("distance", "km", "mile", "mileage"), "Средняя дистанция"),
            (("cancel", "cancell", "rejected", "reject"), "Коэффициент отмены"),
            (("arrival", "arriv", "pickup", "accept"), "Среднее время прибытия водителя"),
            (("revenue", "amount", "total", "sales", "value", "cost"), "Выручка"),
            (("count", "qty", "quantity", "orders", "rides", "trips"), "Количество"),
        )
        for tokens, label in pattern_labels:
            if any(token in lowered for token in tokens):
                return label
        return column_name
