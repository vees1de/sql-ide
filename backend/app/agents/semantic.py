from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass

from app.schemas.dictionary import DictionaryEntryRead
from app.schemas.metadata import ColumnMetadata, RelationshipMetadata, SchemaMetadataResponse, TableMetadata
from app.schemas.query import (
    DimensionMapping,
    FilterMapping,
    IntentPayload,
    SemanticMappingPayload,
)


@dataclass(frozen=True)
class _ResolvedColumn:
    table: str
    column: str
    data_type: str


@dataclass(frozen=True)
class _JoinEdge:
    current_table: str
    next_table: str
    relationship: RelationshipMetadata
    forward: bool


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

    SUM_HINTS = {
        "amount",
        "revenue",
        "sales",
        "total",
        "price",
        "value",
        "cost",
        "fee",
        "payment",
        "profit",
        "balance",
    }
    AVG_HINTS = {
        "avg",
        "average",
        "mean",
        "median",
        "aov",
        "check",
        "amount",
        "value",
        "price",
    }
    DATE_HINTS = {
        "date",
        "day",
        "month",
        "week",
        "time",
        "timestamp",
        "created_at",
        "updated_at",
        "payment_date",
        "order_date",
    }
    TEXT_FALLBACKS = {"name", "title", "label", "type", "status", "category"}
    TIME_DIMENSIONS = {"day", "week", "month"}

    def run(
        self,
        intent: IntentPayload,
        dictionary_entries: list[DictionaryEntryRead],
        dialect: str,
        schema: SchemaMetadataResponse | None = None,
    ) -> SemanticMappingPayload:
        if schema is not None and schema.tables:
            return self._run_schema_aware(intent, dictionary_entries, dialect, schema)

        dictionary_map: dict[str, DictionaryEntryRead] = {}
        for entry in dictionary_entries:
            dictionary_map[entry.term.lower()] = entry
            for synonym in entry.synonyms:
                dictionary_map[synonym.lower()] = entry

        metric_expression = None
        metric_alias = None
        if intent.metric and intent.metric in self.METRICS:
            metric_expression = self.METRICS[intent.metric]["expression"]
            metric_alias = self.METRICS[intent.metric]["alias"]
        elif intent.metric and intent.metric.lower() in dictionary_map:
            metric_expression = dictionary_map[intent.metric.lower()].mapped_expression
            metric_alias = "metric_value"

        dimensions: list[DimensionMapping] = []
        joins: list[str] = []
        tables = {"orders"}
        warnings: list[str] = []
        base_table = "orders"

        if metric_expression:
            metric_tables = self._extract_tables(metric_expression)
            if metric_tables:
                base_table = sorted(metric_tables)[0]
                tables.update(metric_tables)

        for dimension in intent.dimensions:
            expression, alias, join_key = self._resolve_dimension(dimension, dialect)
            if expression is None:
                mapped = dictionary_map.get(dimension.lower())
                if mapped and mapped.object_type == "column":
                    expression = mapped.mapped_expression
                    alias = mapped.column_name or dimension.replace(".", "_")
                    join_key = None
                    tables.update(self._extract_tables(expression))
            if expression is None:
                warnings.append(f"Dimension '{dimension}' could not be mapped by the legacy semantic layer.")
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
                mapped = dictionary_map.get(item.field.lower())
                if mapped and mapped.object_type == "column":
                    expression = mapped.mapped_expression
                    join_key = None
                    tables.update(self._extract_tables(expression))
            if expression is None:
                warnings.append(f"Filter '{item.field}' could not be mapped by the legacy semantic layer.")
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
            base_table=base_table,
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

    def _extract_tables(self, expression: str) -> set[str]:
        matches = re.findall(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\.", expression)
        aliases = {"o", "c", "cp"}
        return {name for name in matches if name not in aliases}

    def _run_schema_aware(
        self,
        intent: IntentPayload,
        dictionary_entries: list[DictionaryEntryRead],
        dialect: str,
        schema: SchemaMetadataResponse,
    ) -> SemanticMappingPayload:
        tables = {table.name: table for table in schema.tables}
        dictionary_lookup = self._build_dictionary_lookup(dictionary_entries)
        measure_candidate, metric_operation = self._pick_metric_candidate(intent.metric, tables, dictionary_lookup)
        time_candidate = self._pick_time_candidate(intent, tables, measure_candidate, dictionary_lookup)

        dimension_candidates: list[tuple[str, _ResolvedColumn, str, str | None]] = []
        filter_candidates: list[tuple[str, _ResolvedColumn, str, object, str | None]] = []
        warnings: list[str] = []

        for dimension in intent.dimensions:
            if dimension in self.TIME_DIMENSIONS:
                continue
            candidate = self._pick_dimension_candidate(dimension, tables, dictionary_lookup)
            if candidate is None:
                warnings.append(f"Dimension '{dimension}' could not be mapped from the connected schema.")
                continue
            dimension_candidates.append((dimension, candidate, self._dimension_alias(dimension, candidate), None))

        for item in intent.filters:
            candidate = self._pick_filter_candidate(item.field, tables, dictionary_lookup)
            if candidate is None:
                warnings.append(f"Filter '{item.field}' could not be mapped from the connected schema.")
                continue
            filter_candidates.append((item.field, candidate, candidate.column, item.value, item.operator or "="))

        base_table = self._choose_base_table(
            measure_candidate=measure_candidate,
            time_candidate=time_candidate,
            dimension_candidates=dimension_candidates,
            filter_candidates=filter_candidates,
            tables=tables,
        )

        required_tables = []
        if measure_candidate is not None:
            required_tables.append(measure_candidate.table)
        if time_candidate is not None:
            required_tables.append(time_candidate.table)
        required_tables.extend(candidate.table for _, candidate, _, _ in dimension_candidates)
        required_tables.extend(candidate.table for _, candidate, _, _, _ in filter_candidates)
        required_tables = [table for table in required_tables if table and table != base_table]

        alias_map, joins, join_warnings = self._build_join_plan(base_table, required_tables, schema.relationships, tables)
        warnings.extend(join_warnings)
        base_alias = alias_map.get(base_table, "t0")

        metric_expression, metric_alias = self._build_metric_expression(
            metric_key=intent.metric,
            measure_candidate=measure_candidate,
            metric_operation=metric_operation,
            base_alias=base_alias,
            alias_map=alias_map,
        )

        time_expression = None
        if time_candidate is not None and time_candidate.table in alias_map:
            time_alias = alias_map[time_candidate.table]
            time_expression = f"{time_alias}.{time_candidate.column}"
        elif time_candidate is not None:
            warnings.append(f"Time column '{time_candidate.table}.{time_candidate.column}' could not be joined.")

        dimension_mappings = []
        for dimension, candidate, alias, _join_key in dimension_candidates:
            table_alias = alias_map.get(candidate.table)
            if table_alias is None:
                warnings.append(f"Dimension '{dimension}' could not be joined from table '{candidate.table}'.")
                continue
            dimension_mappings.append(
                DimensionMapping(
                    key=dimension,
                    label=dimension.replace("_", " ").title(),
                    expression=f"{table_alias}.{candidate.column}",
                    alias=alias,
                    requires_join=None if candidate.table == base_table else candidate.table,
                )
            )

        if time_expression:
            for dimension in intent.dimensions:
                if dimension not in self.TIME_DIMENSIONS:
                    continue
                alias = dimension
                if dimension == "day":
                    expression = self._date_bucket(dialect, "day", time_expression)
                elif dimension == "week":
                    expression = self._date_bucket(dialect, "week", time_expression)
                else:
                    expression = self._date_bucket(dialect, "month", time_expression)
                dimension_mappings.append(
                    DimensionMapping(
                        key=dimension,
                        label=dimension.title(),
                        expression=expression,
                        alias=alias,
                        requires_join=None,
                    )
                )

        filter_mappings = []
        for field, candidate, alias, value, operator in filter_candidates:
            table_alias = alias_map.get(candidate.table)
            if table_alias is None:
                warnings.append(f"Filter '{field}' could not be joined from table '{candidate.table}'.")
                continue
            filter_mappings.append(
                FilterMapping(
                    field=field,
                    expression=f"{table_alias}.{candidate.column}",
                    operator=operator,
                    value=value,
                    requires_join=None if candidate.table == base_table else candidate.table,
                )
            )

        if intent.date_range and time_expression is None:
            warnings.append("A date-like column could not be resolved for the requested period.")

        tables_used = sorted(
            {
                base_table,
                *alias_map.keys(),
                *(candidate.table for _, candidate, _, _ in dimension_candidates),
                *(candidate.table for _, candidate, _, _, _ in filter_candidates),
                *([measure_candidate.table] if measure_candidate is not None else []),
                *([time_candidate.table] if time_candidate is not None else []),
            }
        )

        return SemanticMappingPayload(
            metric_key=intent.metric,
            metric_expression=metric_expression,
            metric_alias=metric_alias,
            time_expression=time_expression,
            base_alias=base_alias,
            dimension_mappings=dimension_mappings,
            filter_mappings=filter_mappings,
            tables=tables_used,
            base_table=base_table,
            joins=joins,
            warnings=warnings,
            dialect=dialect,
        )

    def _build_dictionary_lookup(self, dictionary_entries: list[DictionaryEntryRead]) -> dict[str, list[DictionaryEntryRead]]:
        lookup: dict[str, list[DictionaryEntryRead]] = defaultdict(list)
        for entry in dictionary_entries:
            keys = {self._normalize_token(entry.term)}
            keys.update(self._normalize_token(synonym) for synonym in entry.synonyms)
            for key in keys:
                if key:
                    lookup[key].append(entry)
        return lookup

    def _pick_metric_candidate(
        self,
        metric_key: str | None,
        tables: dict[str, TableMetadata],
        dictionary_lookup: dict[str, list[DictionaryEntryRead]],
    ) -> tuple[_ResolvedColumn | None, str]:
        if not metric_key:
            return (None, "sum")
        if metric_key == "order_count":
            return (None, "count")
        dictionary_candidate = self._dictionary_candidate(metric_key, tables, dictionary_lookup, prefer_text=False, prefer_metric=True)
        if dictionary_candidate is not None and self._is_numeric_type(dictionary_candidate.data_type):
            return (dictionary_candidate, "avg" if metric_key == "avg_order_value" else "sum")

        score_kind = "avg" if metric_key == "avg_order_value" else "sum"
        best: _ResolvedColumn | None = None
        best_score = -1
        for table in tables.values():
            for column in table.columns:
                if not self._is_numeric_type(column.type):
                    continue
                score = self._score_measure_column(metric_key, table.name, column)
                if score > best_score:
                    best = _ResolvedColumn(table=table.name, column=column.name, data_type=column.type)
                    best_score = score

        if best is None:
            return (None, "count")
        return (best, score_kind)

    def _pick_time_candidate(
        self,
        intent: IntentPayload,
        tables: dict[str, TableMetadata],
        measure_candidate: _ResolvedColumn | None,
        dictionary_lookup: dict[str, list[DictionaryEntryRead]],
    ) -> _ResolvedColumn | None:
        need_time = bool(intent.date_range or any(dim in self.TIME_DIMENSIONS for dim in intent.dimensions))
        if not need_time:
            return None

        dictionary_candidate = self._dictionary_candidate("date", tables, dictionary_lookup, prefer_text=False, prefer_metric=False)
        if dictionary_candidate is not None and self._is_date_type(dictionary_candidate.data_type):
            return dictionary_candidate

        best: _ResolvedColumn | None = None
        best_score = -1
        for table in tables.values():
            for column in table.columns:
                if not self._is_date_type(column.type):
                    continue
                score = self._score_time_column(table.name, column)
                if measure_candidate is not None and table.name == measure_candidate.table:
                    score += 3
                if score > best_score:
                    best = _ResolvedColumn(table=table.name, column=column.name, data_type=column.type)
                    best_score = score

        return best

    def _pick_dimension_candidate(
        self,
        dimension: str,
        tables: dict[str, TableMetadata],
        dictionary_lookup: dict[str, list[DictionaryEntryRead]],
    ) -> _ResolvedColumn | None:
        dictionary_candidate = self._dictionary_candidate(dimension, tables, dictionary_lookup, prefer_text=True, prefer_metric=False)
        if dictionary_candidate is not None:
            return dictionary_candidate

        best: _ResolvedColumn | None = None
        best_score = -1
        normalized = self._normalize_token(dimension)
        for table in tables.values():
            for column in table.columns:
                score = self._score_dimension_column(dimension, normalized, table.name, column)
                if score > best_score:
                    best = _ResolvedColumn(table=table.name, column=column.name, data_type=column.type)
                    best_score = score

        return best if best_score > 0 else None

    def _pick_filter_candidate(
        self,
        field: str,
        tables: dict[str, TableMetadata],
        dictionary_lookup: dict[str, list[DictionaryEntryRead]],
    ) -> _ResolvedColumn | None:
        dictionary_candidate = self._dictionary_candidate(field, tables, dictionary_lookup, prefer_text=True, prefer_metric=False)
        if dictionary_candidate is not None:
            return dictionary_candidate

        best: _ResolvedColumn | None = None
        best_score = -1
        normalized = self._normalize_token(field)
        for table in tables.values():
            for column in table.columns:
                score = self._score_dimension_column(field, normalized, table.name, column)
                if score > best_score:
                    best = _ResolvedColumn(table=table.name, column=column.name, data_type=column.type)
                    best_score = score

        return best if best_score > 0 else None

    def _dimension_alias(self, dimension: str, candidate: _ResolvedColumn) -> str:
        normalized_dimension = self._normalize_token(dimension)
        candidate_name = self._normalize_token(candidate.column)
        if normalized_dimension in self.TIME_DIMENSIONS:
            return normalized_dimension
        if candidate_name == normalized_dimension:
            return candidate.column
        if candidate_name in {"name", "title", "label"}:
            return f"{normalized_dimension}_{candidate.column}"
        return candidate.column

    def _dictionary_candidate(
        self,
        name: str,
        tables: dict[str, TableMetadata],
        dictionary_lookup: dict[str, list[DictionaryEntryRead]],
        *,
        prefer_text: bool,
        prefer_metric: bool,
    ) -> _ResolvedColumn | None:
        normalized = self._normalize_token(name)
        candidates = list(dictionary_lookup.get(normalized, []))
        if not candidates:
            variants = self._name_variants(name)
            for variant in variants:
                candidates.extend(dictionary_lookup.get(variant, []))

        for entry in candidates:
            if entry.table_name and entry.column_name and entry.table_name in tables:
                table = tables[entry.table_name]
                column = self._find_column(table, entry.column_name)
                if column is not None:
                    return _ResolvedColumn(table=table.name, column=column.name, data_type=column.type)
            if entry.object_type == "table" and entry.table_name in tables:
                column = self._best_text_column(tables[entry.table_name], prefer_metric=prefer_metric, prefer_text=prefer_text)
                if column is not None:
                    return _ResolvedColumn(table=entry.table_name, column=column.name, data_type=column.type)
        return None

    def _choose_base_table(
        self,
        *,
        measure_candidate: _ResolvedColumn | None,
        time_candidate: _ResolvedColumn | None,
        dimension_candidates: list[tuple[str, _ResolvedColumn, str, str | None]],
        filter_candidates: list[tuple[str, _ResolvedColumn, str, object, str | None]],
        tables: dict[str, TableMetadata],
    ) -> str:
        scores: dict[str, int] = defaultdict(int)
        if measure_candidate is not None:
            scores[measure_candidate.table] += 5
        if time_candidate is not None:
            scores[time_candidate.table] += 4
        for _dimension, candidate, _alias, _join_key in dimension_candidates:
            scores[candidate.table] += 3
        for _field, candidate, _alias, _value, _operator in filter_candidates:
            scores[candidate.table] += 3

        if not scores:
            return next(iter(tables.keys()))

        return max(
            scores.items(),
            key=lambda item: (
                item[1],
                item[0] == (measure_candidate.table if measure_candidate else ""),
                item[0] == (time_candidate.table if time_candidate else ""),
            ),
        )[0]

    def _build_join_plan(
        self,
        base_table: str,
        required_tables: list[str],
        relationships: list[RelationshipMetadata],
        tables: dict[str, TableMetadata],
    ) -> tuple[dict[str, str], list[str], list[str]]:
        graph = self._build_relationship_graph(relationships, tables)
        alias_map: dict[str, str] = {base_table: "t0"}
        joins: list[str] = []
        warnings: list[str] = []
        seen_join_sql: set[str] = set()
        next_alias_index = 1

        for target_table in self._dedupe(required_tables):
            if target_table == base_table:
                continue
            path = self._find_join_path(base_table, target_table, graph)
            if not path:
                warnings.append(f"Could not infer a join path from '{base_table}' to '{target_table}'.")
                continue
            current_table = base_table
            for step in path:
                if step.next_table not in alias_map:
                    alias_map[step.next_table] = f"t{next_alias_index}"
                    next_alias_index += 1
                join_sql = self._format_join(step, alias_map[current_table], alias_map[step.next_table])
                if join_sql not in seen_join_sql:
                    joins.append(join_sql)
                    seen_join_sql.add(join_sql)
                current_table = step.next_table

        return alias_map, joins, warnings

    def _build_relationship_graph(
        self,
        relationships: list[RelationshipMetadata],
        tables: dict[str, TableMetadata],
    ) -> dict[str, list[_JoinEdge]]:
        graph: dict[str, list[_JoinEdge]] = defaultdict(list)
        seen_edges: set[tuple[str, str, str, str]] = set()

        def add_edge(from_table: str, to_table: str, relationship: RelationshipMetadata, forward: bool) -> None:
            key = (from_table, to_table, relationship.from_column, relationship.to_column)
            if key in seen_edges:
                return
            seen_edges.add(key)
            graph[from_table].append(
                _JoinEdge(
                    current_table=from_table,
                    next_table=to_table,
                    relationship=relationship,
                    forward=forward,
                )
            )

        for relationship in relationships:
            if relationship.from_table not in tables or relationship.to_table not in tables:
                continue
            add_edge(relationship.from_table, relationship.to_table, relationship, True)
            add_edge(relationship.to_table, relationship.from_table, relationship, False)

        for table in tables.values():
            for column in table.columns:
                if not column.name.lower().endswith("_id") or column.name.lower() == "id":
                    continue
                root = column.name[:-3]
                for target_table in self._table_name_variants(root):
                    if target_table == table.name or target_table not in tables:
                        continue
                    target_columns = {candidate.name.lower() for candidate in tables[target_table].columns}
                    if "id" not in target_columns:
                        continue
                    relationship = RelationshipMetadata(
                        from_table=table.name,
                        from_column=column.name,
                        to_table=target_table,
                        to_column="id",
                        relation_type="inferred_fk",
                        cardinality="many_to_one",
                    )
                    add_edge(table.name, target_table, relationship, True)
                    add_edge(target_table, table.name, relationship, False)

        return graph

    def _find_join_path(
        self,
        base_table: str,
        target_table: str,
        graph: dict[str, list[_JoinEdge]],
    ) -> list[_JoinEdge] | None:
        queue: deque[tuple[str, list[_JoinEdge]]] = deque([(base_table, [])])
        visited = {base_table}

        while queue:
            current_table, path = queue.popleft()
            if current_table == target_table:
                return path
            for edge in graph.get(current_table, []):
                if edge.next_table in visited:
                    continue
                visited.add(edge.next_table)
                queue.append((edge.next_table, [*path, edge]))

        return None

    def _build_metric_expression(
        self,
        *,
        metric_key: str | None,
        measure_candidate: _ResolvedColumn | None,
        metric_operation: str,
        base_alias: str,
        alias_map: dict[str, str],
    ) -> tuple[str, str]:
        if metric_operation == "count":
            return ("COUNT(*)", "record_count")

        if measure_candidate is None:
            alias = "avg_value" if metric_operation == "avg" else "total_value"
            return (f"{metric_operation.upper()}(*)", alias)

        alias = alias_map.get(measure_candidate.table, base_alias)
        if metric_operation == "avg":
            metric_alias = "avg_order_value" if metric_key == "avg_order_value" else f"avg_{measure_candidate.column}"
        else:
            metric_alias = "total_revenue" if metric_key == "revenue" else f"total_{measure_candidate.column}"
        return (f"{metric_operation.upper()}({alias}.{measure_candidate.column})", metric_alias)

    def _score_measure_column(self, metric_key: str | None, table_name: str, column: ColumnMetadata) -> int:
        type_name = column.type.lower()
        if not self._is_numeric_type(type_name):
            return -1

        score = 1
        column_name = self._normalize_token(column.name)
        table_name_norm = self._normalize_token(table_name)
        metric_name = self._normalize_token(metric_key or "")

        if metric_name in self._name_variants(column.name):
            score += 6
        if metric_key == "avg_order_value" and any(hint in column_name for hint in self.AVG_HINTS):
            score += 5
        if metric_key == "revenue" and any(hint in column_name for hint in self.SUM_HINTS):
            score += 5
        if any(hint in column_name for hint in self.SUM_HINTS):
            score += 3
        if any(hint in column_name for hint in self.AVG_HINTS):
            score += 2
        if column_name == "id" or column_name.endswith("_id"):
            score -= 4
        if table_name_norm in metric_name:
            score += 1
        return score

    def _score_time_column(self, table_name: str, column: ColumnMetadata) -> int:
        type_name = column.type.lower()
        if not self._is_date_type(type_name):
            return -1

        score = 1
        column_name = self._normalize_token(column.name)
        if any(hint in column_name for hint in self.DATE_HINTS):
            score += 5
        if column_name in {"date", "day", "month", "week"}:
            score += 4
        if column_name.endswith("_date") or column_name.endswith("_at"):
            score += 4
        if table_name.lower() in column_name:
            score += 1
        return score

    def _score_dimension_column(self, dimension: str, normalized_dimension: str, table_name: str, column: ColumnMetadata) -> int:
        column_name = self._normalize_token(column.name)
        table_name_norm = self._normalize_token(table_name)
        type_name = column.type.lower()
        score = 0

        if column_name == normalized_dimension:
            score += 10
        if normalized_dimension in self._name_variants(column.name):
            score += 8
        if normalized_dimension in self._table_name_variants(table_name):
            if column_name in self.TEXT_FALLBACKS or self._is_text_type(type_name):
                score += 7
        if any(token in column_name for token in self._tokens(normalized_dimension)):
            score += 4
        if self._is_text_type(type_name):
            score += 1
        if column_name in self.TEXT_FALLBACKS:
            score += 1
        if table_name_norm == normalized_dimension and column_name in {"name", "title", "label"}:
            score += 3
        return score

    def _find_column(self, table: TableMetadata, column_name: str) -> ColumnMetadata | None:
        for column in table.columns:
            if column.name == column_name:
                return column
        return None

    def _best_text_column(
        self,
        table: TableMetadata,
        *,
        prefer_metric: bool,
        prefer_text: bool,
    ) -> ColumnMetadata | None:
        best: ColumnMetadata | None = None
        best_score = -1
        for column in table.columns:
            score = 0
            name = self._normalize_token(column.name)
            type_name = column.type.lower()
            if self._is_text_type(type_name):
                score += 2
            if name in self.TEXT_FALLBACKS:
                score += 5
            if name == "name":
                score += 3
            if name.endswith("_name"):
                score += 2
            if prefer_text and self._is_text_type(type_name):
                score += 1
            if prefer_metric and name == "name":
                score += 1
            if score > best_score:
                best = column
                best_score = score
        return best

    def _build_relationships(
        self,
        relationships: list[RelationshipMetadata],
    ) -> list[RelationshipMetadata]:
        deduped: dict[tuple[str, str, str, str, str], RelationshipMetadata] = {}
        for relationship in relationships:
            key = (
                relationship.from_table,
                relationship.from_column,
                relationship.to_table,
                relationship.to_column,
                relationship.relation_type,
            )
            deduped[key] = relationship
        return list(deduped.values())

    def _normalize_token(self, value: str | None) -> str:
        if value is None:
            return ""
        return re.sub(r"[^0-9a-zа-я]+", "", value.casefold())

    def _tokens(self, value: str) -> list[str]:
        return [token for token in re.split(r"[_\W]+", value.casefold()) if token]

    def _name_variants(self, value: str) -> set[str]:
        normalized = self._normalize_token(value)
        variants = {normalized}
        if normalized.endswith("ies"):
            variants.add(normalized[:-3] + "y")
        if normalized.endswith("s") and len(normalized) > 1:
            variants.add(normalized[:-1])
        else:
            variants.add(normalized + "s")
        return {item for item in variants if item}

    def _table_name_variants(self, value: str) -> set[str]:
        normalized = self._normalize_token(value)
        return self._name_variants(normalized)

    def _dedupe(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def _format_join(self, edge: _JoinEdge, current_alias: str, next_alias: str) -> str:
        relationship = edge.relationship
        if edge.forward:
            return (
                f"LEFT JOIN {edge.next_table} {next_alias} "
                f"ON {current_alias}.{relationship.from_column} = {next_alias}.{relationship.to_column}"
            )
        return (
            f"LEFT JOIN {edge.next_table} {next_alias} "
            f"ON {current_alias}.{relationship.to_column} = {next_alias}.{relationship.from_column}"
        )

    def _is_numeric_type(self, type_name: str) -> bool:
        return any(
            marker in type_name
            for marker in ("int", "numeric", "decimal", "float", "double", "real", "money", "number")
        )

    def _is_date_type(self, type_name: str) -> bool:
        return any(marker in type_name for marker in ("date", "time", "timestamp", "datetime"))

    def _is_text_type(self, type_name: str) -> bool:
        return any(marker in type_name for marker in ("char", "text", "clob", "string", "uuid"))

    def _date_bucket(self, dialect: str, grain: str, expression: str) -> str:
        if dialect == "postgresql":
            if grain == "day":
                return f"date_trunc('day', {expression})"
            if grain == "week":
                return f"date_trunc('week', {expression})"
            return f"date_trunc('month', {expression})"
        if grain == "day":
            return f"date({expression})"
        if grain == "week":
            return f"date({expression}, 'weekday 1', '-7 days')"
        return f"date({expression}, 'start of month')"
