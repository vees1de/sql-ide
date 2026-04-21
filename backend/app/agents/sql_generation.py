from __future__ import annotations

from datetime import timedelta

from app.agents.helpers import shift_year, subtract_months
from app.schemas.query import DateRange, IntentPayload, SemanticMappingPayload


class SQLGenerationAgent:
    def run(self, intent: IntentPayload, semantic: SemanticMappingPayload) -> str:
        if intent.metric is None or semantic.metric_expression is None or semantic.metric_alias is None:
            raise ValueError("Metric mapping is required to generate SQL.")

        if intent.comparison == "previous_year":
            effective_range = intent.date_range or self._default_comparison_range()
            return self._build_previous_year_comparison_query(intent, semantic, effective_range)

        return self._build_aggregate_query(intent, semantic, intent.date_range)

    def _build_aggregate_query(
        self,
        intent: IntentPayload,
        semantic: SemanticMappingPayload,
        date_range: DateRange | None,
    ) -> str:
        select_parts = []
        group_indices = []

        for index, mapping in enumerate(semantic.dimension_mappings, start=1):
            select_parts.append(f"{mapping.expression} AS {mapping.alias}")
            group_indices.append(str(index))
        select_parts.append(f"{semantic.metric_expression} AS {semantic.metric_alias}")

        where_clauses = self._build_where_clauses(semantic, date_range)
        joins = "\n".join(semantic.joins)
        from_clause, joins = self._source_sql(semantic, joins)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        group_sql = f"GROUP BY {', '.join(group_indices)}" if group_indices else ""
        order_sql = f"ORDER BY {', '.join(group_indices)}" if group_indices else ""

        return "\n".join(
            part
            for part in [
                f"SELECT {', '.join(select_parts)}",
                from_clause,
                joins,
                where_sql,
                group_sql,
                order_sql,
            ]
            if part
        )

    def _build_previous_year_comparison_query(
        self,
        intent: IntentPayload,
        semantic: SemanticMappingPayload,
        date_range: DateRange,
    ) -> str:
        previous_range = DateRange(
            kind="absolute",
            start=shift_year(date_range.start, -1) if date_range.start else None,
            end=shift_year(date_range.end, -1) if date_range.end else None,
        )
        current_sql = self._build_period_query(
            semantic=semantic,
            label="current_period",
            date_range=date_range,
            align_previous_year=False,
        )
        previous_sql = self._build_period_query(
            semantic=semantic,
            label="previous_year",
            date_range=previous_range,
            align_previous_year=True,
        )
        order_positions = [str(index) for index in range(1, len(semantic.dimension_mappings) + 2)]
        order_sql = f"ORDER BY {', '.join(order_positions)}"
        return "\n".join(
            [
                current_sql,
                "UNION ALL",
                previous_sql,
                order_sql,
            ]
        )

    def _build_period_query(
        self,
        semantic: SemanticMappingPayload,
        label: str,
        date_range: DateRange,
        align_previous_year: bool,
    ) -> str:
        select_parts = []
        group_indices = []

        for index, mapping in enumerate(semantic.dimension_mappings, start=1):
            expression = mapping.expression
            if align_previous_year and mapping.key in {"day", "week", "month"} and semantic.time_expression:
                expression = self._align_date_expression(semantic.dialect, mapping.key, semantic.time_expression or mapping.expression)
            select_parts.append(f"{expression} AS {mapping.alias}")
            group_indices.append(str(index))

        select_parts.append(f"'{label}' AS period_label")
        label_index = len(select_parts)
        select_parts.append(f"{semantic.metric_expression} AS {semantic.metric_alias}")

        where_clauses = self._build_where_clauses(semantic, date_range)
        joins = "\n".join(semantic.joins)
        from_clause, joins = self._source_sql(semantic, joins)
        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        group_sql = f"GROUP BY {', '.join(group_indices + [str(label_index)])}" if group_indices else f"GROUP BY {label_index}"

        return "\n".join(
            part
            for part in [
                f"SELECT {', '.join(select_parts)}",
                from_clause,
                joins,
                where_sql,
                group_sql,
            ]
            if part
        )

    def _build_where_clauses(self, semantic: SemanticMappingPayload, date_range: DateRange | None) -> list[str]:
        clauses: list[str] = []
        if semantic.time_expression and date_range:
            if date_range.start:
                clauses.append(f"{semantic.time_expression} >= {self._quote(date_range.start.isoformat())}")
            if date_range.end:
                exclusive_end = date_range.end + timedelta(days=1)
                clauses.append(f"{semantic.time_expression} < {self._quote(exclusive_end.isoformat())}")

        for filter_mapping in semantic.filter_mappings:
            operator = filter_mapping.operator or "="
            clauses.append(f"{filter_mapping.expression} {operator} {self._quote(filter_mapping.value)}")

        return clauses

    def _align_date_expression(self, dialect: str, grain: str, time_expression: str) -> str:
        if dialect == "postgresql":
            if grain == "day":
                return f"date_trunc('day', {time_expression} + interval '1 year')"
            if grain == "week":
                return f"date_trunc('week', {time_expression} + interval '1 year')"
            return f"date_trunc('month', {time_expression} + interval '1 year')"
        if grain == "day":
            return f"date({time_expression}, '+1 year')"
        if grain == "week":
            return f"date(date({time_expression}, '+1 year'), 'weekday 1', '-7 days')"
        return f"date(date({time_expression}, '+1 year'), 'start of month')"

    def _default_comparison_range(self) -> DateRange:
        from datetime import date

        today = date.today()
        return DateRange(kind="relative", start=subtract_months(today, 6), end=today, lookback_value=6, lookback_unit="months")

    def _quote(self, value: object) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    def _source_sql(self, semantic: SemanticMappingPayload, joins: str) -> tuple[str, str]:
        base_alias = semantic.base_alias or "t0"
        return (f"FROM {self._quote_identifier(semantic.base_table)} {base_alias}", joins)

    def _quote_identifier(self, value: str) -> str:
        parts = [part for part in value.split(".") if part]
        if not parts:
            return '""'
        quoted_parts = []
        for part in parts:
            quoted_parts.append('"' + part.replace('"', '""') + '"')
        return ".".join(quoted_parts)
