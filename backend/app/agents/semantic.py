from __future__ import annotations

from app.schemas.dictionary import DictionaryEntryRead
from app.schemas.query import (
    DimensionMapping,
    FilterMapping,
    IntentPayload,
    SemanticMappingPayload,
)


class SemanticMappingAgent:
    METRICS = {
        "revenue": {"expression": "SUM(o.revenue)", "alias": "total_revenue"},
        "order_count": {"expression": "COUNT(o.id)", "alias": "total_orders"},
        "avg_order_value": {"expression": "AVG(o.revenue)", "alias": "avg_order_value"},
    }
    DYNAMIC_JOINS = {
        "customer": "JOIN customers c ON c.id = o.customer_id",
        "campaign": "LEFT JOIN campaigns cp ON cp.id = o.campaign_id",
    }

    def run(
        self,
        intent: IntentPayload,
        dictionary_entries: list[DictionaryEntryRead],
        dialect: str,
    ) -> SemanticMappingPayload:
        dictionary_map = {
            entry.term.lower(): entry.mapped_expression
            for entry in dictionary_entries
        }

        metric_expression = None
        metric_alias = None
        if intent.metric and intent.metric in self.METRICS:
            metric_expression = self.METRICS[intent.metric]["expression"]
            metric_alias = self.METRICS[intent.metric]["alias"]
        elif intent.metric and intent.metric.lower() in dictionary_map:
            metric_expression = dictionary_map[intent.metric.lower()]
            metric_alias = "metric_value"

        dimensions: list[DimensionMapping] = []
        joins: list[str] = []
        tables = {"orders"}
        warnings: list[str] = []

        for dimension in intent.dimensions:
            expression, alias, join_key = self._resolve_dimension(dimension, dialect)
            if expression is None:
                warnings.append(f"Dimension '{dimension}' is not supported in the MVP semantic layer.")
                continue
            dimensions.append(
                DimensionMapping(
                    key=dimension,
                    label=dimension.replace("_", " ").title(),
                    expression=expression,
                    alias=alias,
                    requires_join=join_key,
                )
            )
            if join_key == "customer":
                tables.add("customers")
            elif join_key == "campaign":
                tables.add("campaigns")
            if join_key:
                joins.append(self.DYNAMIC_JOINS[join_key])

        filter_mappings: list[FilterMapping] = []
        for item in intent.filters:
            expression, join_key = self._resolve_filter_expression(item.field)
            if expression is None:
                warnings.append(f"Filter '{item.field}' is not supported in the MVP semantic layer.")
                continue
            if join_key == "customer":
                tables.add("customers")
            elif join_key == "campaign":
                tables.add("campaigns")
            if join_key:
                joins.append(self.DYNAMIC_JOINS[join_key])
            filter_mappings.append(
                FilterMapping(
                    field=item.field,
                    expression=expression,
                    operator=item.operator,
                    value=item.value,
                    requires_join=join_key,
                )
            )

        unique_joins = list(dict.fromkeys(joins))
        return SemanticMappingPayload(
            metric_key=intent.metric,
            metric_expression=metric_expression,
            metric_alias=metric_alias,
            dimension_mappings=dimensions,
            filter_mappings=filter_mappings,
            tables=sorted(tables),
            joins=unique_joins,
            warnings=warnings,
            dialect=dialect,
        )

    def _resolve_dimension(self, key: str, dialect: str) -> tuple[str | None, str | None, str | None]:
        if key == "month":
            return (self._date_bucket(dialect, "month"), "month", None)
        if key == "week":
            return (self._date_bucket(dialect, "week"), "week", None)
        if key == "day":
            return (self._date_bucket(dialect, "day"), "day", None)
        if key == "region":
            return ("c.region", "region", "customer")
        if key == "city":
            return ("c.city", "city", "customer")
        if key == "segment":
            return ("c.segment", "segment", "customer")
        if key == "channel":
            return ("cp.channel", "channel", "campaign")
        if key == "campaign":
            return ("cp.name", "campaign_name", "campaign")
        return (None, None, None)

    def _resolve_filter_expression(self, field: str) -> tuple[str | None, str | None]:
        if field in {"city", "region", "segment"}:
            return (f"c.{field}", "customer")
        if field == "channel":
            return ("cp.channel", "campaign")
        if field == "campaign":
            return ("cp.name", "campaign")
        return (None, None)

    def _date_bucket(self, dialect: str, grain: str) -> str:
        if dialect == "postgresql":
            if grain == "day":
                return "date_trunc('day', o.order_date)"
            if grain == "week":
                return "date_trunc('week', o.order_date)"
            return "date_trunc('month', o.order_date)"
        if grain == "day":
            return "date(o.order_date)"
        if grain == "week":
            return "date(o.order_date, 'weekday 1', '-7 days')"
        return "date(o.order_date, 'start of month')"
