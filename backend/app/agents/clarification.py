from __future__ import annotations

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


class ClarificationAgent:
    """Builds clarification UI payload; optional schema grounds choices in real tables/columns (RAG-style context)."""

    def run(self, intent: IntentPayload, schema: SchemaMetadataResponse | None = None) -> dict:
        options: list[str] = []
        if "sales" in intent.ambiguities:
            options = ["Выручка", "Количество заказов"]
        elif intent.metric is None:
            options = ["Выручка", "Количество заказов", "Средний чек"]

        if not options and schema and schema.tables:
            options = self._options_from_schema(schema)
        if not options:
            options = ["Уточнить в следующем сообщении (метрика, таблица или период)"]

        return {
            "question": intent.clarification_question,
            "ambiguities": intent.ambiguities,
            "options": options,
            "schema_tables": [t.name for t in schema.tables[:12]] if schema else [],
        }

    def _options_from_schema(self, schema: SchemaMetadataResponse) -> list[str]:
        """Prefer numeric / measure-like columns; fall back to table names."""
        out: list[str] = []
        for table in schema.tables:
            metric_cols = [c.name for c in table.columns if self._looks_like_metric_column(c)][:4]
            if metric_cols:
                joined = ", ".join(metric_cols)
                out.append(f"Таблица «{table.name}»: метрики {joined}")
            if len(out) >= 6:
                break
        if out:
            return out[:6]
        return [f"Таблица «{t.name}»" for t in schema.tables[:6]]

    @staticmethod
    def _looks_like_metric_column(column: ColumnMetadata) -> bool:
        type_lower = column.type.lower()
        if any(x in type_lower for x in ("int", "numeric", "decimal", "float", "double", "real", "money")):
            return True
        name_lower = column.name.lower()
        return any(h in name_lower for h in _METRIC_NAME_HINTS)
