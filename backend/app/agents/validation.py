from __future__ import annotations

from typing import Any

from sqlglot import expressions as exp
from sqlglot import parse, parse_one

from app.core.config import settings
from app.schemas.metadata import SchemaMetadataResponse
from app.schemas.query import ValidationPayload
from app.schemas.semantic_catalog import SemanticCatalog, SemanticColumn


class SQLValidationAgent:
    def run(
        self,
        sql: str,
        dialect: str,
        allowed_tables: list[str] | tuple[str, ...] | None = None,
        schema: SchemaMetadataResponse | None = None,
        semantic_catalog: SemanticCatalog | None = None,
    ) -> ValidationPayload:
        errors: list[str] = []
        warnings: list[str] = []
        confidence_reasons: list[str] = []

        try:
            statements = parse(sql, read=self._read_dialect(dialect))
        except Exception as exc:  # noqa: BLE001
            return ValidationPayload(valid=False, sql=sql, errors=[f"SQL parse error: {exc}"])

        if len(statements) != 1:
            errors.append("Only a single SQL statement is allowed.")
            return ValidationPayload(valid=False, sql=sql, errors=errors)

        parsed = parse_one(sql, read=self._read_dialect(dialect))
        if not (parsed.find(exp.Select) or isinstance(parsed, exp.Select) or isinstance(parsed, exp.Union)):
            errors.append("Only SELECT queries are allowed.")

        dangerous_nodes = [
            node
            for node_name in ("Insert", "Update", "Delete", "Drop", "Alter", "Create", "Command")
            if (node := getattr(exp, node_name, None)) is not None
        ]
        for dangerous_node in dangerous_nodes:
            if parsed.find(dangerous_node):
                errors.append("Dangerous SQL operation detected.")
                break

        tables = sorted({table.name for table in parsed.find_all(exp.Table)})
        if allowed_tables is not None:
            effective_allowed_tables = tuple(str(table) for table in allowed_tables)
            unknown_tables = sorted(set(tables) - set(effective_allowed_tables))
            if unknown_tables:
                errors.append(f"Query references tables outside the whitelist: {', '.join(unknown_tables)}.")

        # --- Semantic lint checks (non-blocking, warning-only) ---
        self._detect_bogus_cross_join(parsed, warnings)
        if schema is not None:
            self._detect_snapshot_join_without_aggregation(parsed, schema, warnings)
        confidence_level = None
        if semantic_catalog is not None:
            confidence_level, confidence_reasons = self._semantic_round_trip(
                parsed,
                semantic_catalog,
                warnings,
                errors,
            )

        parsed = self._apply_row_limit(parsed, warnings)
        final_sql = self.format_sql(parsed.sql(pretty=True, dialect=self._read_dialect(dialect)), dialect)

        return ValidationPayload(
            valid=not errors,
            sql=final_sql,
            tables=tables,
            warnings=warnings,
            errors=errors,
            semantic_confidence_level=confidence_level,
            semantic_confidence_reasons=confidence_reasons,
        )

    # ------------------------------------------------------------------
    # Semantic lint: uncorrelated CROSS JOIN that duplicates a scalar value.
    # Example anti-pattern:
    #   SELECT l.name, c.cnt
    #   FROM league l
    #   CROSS JOIN (SELECT COUNT(*) AS cnt FROM player_attributes ...) c
    # → every league gets the same global count, which is almost never intended.
    # ------------------------------------------------------------------
    def _detect_bogus_cross_join(
        self, parsed: exp.Expression, warnings: list[str]
    ) -> None:
        try:
            selects = list(parsed.find_all(exp.Select))
        except Exception:  # noqa: BLE001
            return

        outer_table_aliases: set[str] = set()
        for select in selects:
            for join in select.args.get("joins") or []:
                kind = (join.args.get("kind") or "").upper()
                side = (join.args.get("side") or "").upper()
                has_on = bool(join.args.get("on") or join.args.get("using"))

                # Looks like a CROSS JOIN (explicit) or an implicit join without ON.
                is_cross_like = kind == "CROSS" or side == "CROSS" or (not has_on and kind != "LATERAL")
                if not is_cross_like:
                    continue

                right = join.this
                # Drill into aliased subqueries.
                if isinstance(right, exp.Alias):
                    right = right.this
                if isinstance(right, (exp.Subquery, exp.Paren)):
                    right = right.this

                if not isinstance(right, exp.Select):
                    continue

                # Scalar subquery: exactly one projection AND it is an aggregate
                # function (COUNT/SUM/AVG/MIN/MAX) OR has no FROM at all.
                projections = right.expressions or []
                if len(projections) != 1:
                    continue

                if self._is_aggregate_scalar(projections[0]):
                    warnings.append(
                        "Подозрительный CROSS JOIN: правая часть — подзапрос с глобальным агрегатом "
                        "без связи с левой таблицей. Каждая строка левой таблицы получит одно и то же "
                        "значение. Вероятно, нужен коррелированный подзапрос или JOIN по ключу."
                    )
                    return

    @staticmethod
    def _is_aggregate_scalar(expr: exp.Expression) -> bool:
        # unwrap alias
        if isinstance(expr, exp.Alias):
            expr = expr.this
        agg_types = (exp.Count, exp.Sum, exp.Avg, exp.Min, exp.Max)
        if isinstance(expr, agg_types):
            return True
        # Any AggFunc descendant counts too
        return any(isinstance(node, agg_types) for node in expr.walk())

    # ------------------------------------------------------------------
    # Semantic lint: joining a snapshot/time-series table to its parent
    # without DISTINCT ON / GROUP BY / date = MAX(date). Produces row
    # multiplication (the "Messi bug").
    # ------------------------------------------------------------------
    _DATE_COL_HINTS = ("date", "timestamp", "updated", "created", "period")

    def _detect_snapshot_join_without_aggregation(
        self,
        parsed: exp.Expression,
        schema: SchemaMetadataResponse,
        warnings: list[str],
    ) -> None:
        try:
            tables_in_query = {t.name for t in parsed.find_all(exp.Table)}
        except Exception:  # noqa: BLE001
            return

        snapshot_tables = self._find_snapshot_tables(schema, tables_in_query)
        if not snapshot_tables:
            return

        try:
            selects = list(parsed.find_all(exp.Select))
        except Exception:  # noqa: BLE001
            return

        for select in selects:
            joins = select.args.get("joins") or []
            if not joins:
                continue

            # Flags that make the join safe.
            has_group_by = bool(select.args.get("group"))
            has_distinct = bool(select.args.get("distinct"))
            # DISTINCT ON appears as distinct.on
            has_distinct_on = has_distinct and bool(getattr(select.args.get("distinct"), "args", {}).get("on"))
            has_max_date_filter = self._has_max_date_subquery(select)

            if has_group_by or has_distinct or has_distinct_on or has_max_date_filter:
                continue

            # At least one joined table is a snapshot and it has no aggregation safeguard.
            snapshot_hits: list[str] = []
            for join in joins:
                right = join.this
                if isinstance(right, exp.Alias):
                    right = right.this
                name = None
                if isinstance(right, exp.Table):
                    name = right.name
                if name and name in snapshot_tables:
                    snapshot_hits.append(name)

            # Also check the main FROM clause.
            from_expr = select.args.get("from")
            if from_expr is not None:
                for table_node in from_expr.find_all(exp.Table):
                    if table_node.name in snapshot_tables:
                        # Only warn when the snapshot is actually joined (otherwise single-table scan is fine)
                        if joins:
                            snapshot_hits.append(table_node.name)
                        break

            if snapshot_hits:
                unique = sorted(set(snapshot_hits))
                warnings.append(
                    f"Таблица {', '.join(unique)} похожа на time-series snapshot "
                    "(есть колонка дата + внешний ключ). JOIN без GROUP BY / DISTINCT ON / "
                    "фильтра `date = MAX(date)` приведёт к дублям: одна сущность получит по строке "
                    "на каждую дату."
                )
                return

    @classmethod
    def _find_snapshot_tables(
        cls, schema: SchemaMetadataResponse, tables_in_query: set[str]
    ) -> set[str]:
        result: set[str] = set()
        # A table is a snapshot if it has (a) a date-like column AND
        # (b) is referenced as a FK target or contains a column ending in _id / _api_id.
        for table in schema.tables:
            if table.name not in tables_in_query:
                continue
            has_date = any(
                any(hint in (c.name or "").lower() for hint in cls._DATE_COL_HINTS)
                or any(hint in (c.type or "").lower() for hint in ("date", "timestamp"))
                for c in table.columns
            )
            has_fk_like = any(
                (c.name or "").lower().endswith(("_id", "_api_id"))
                and (c.name or "").lower() != "id"
                for c in table.columns
            )
            if has_date and has_fk_like:
                result.add(table.name)
        return result

    @staticmethod
    def _has_max_date_subquery(select: exp.Select) -> bool:
        where = select.args.get("where")
        if where is None:
            return False
        for subq in where.find_all(exp.Select):
            for node in subq.expressions or []:
                unwrapped = node.this if isinstance(node, exp.Alias) else node
                if isinstance(unwrapped, exp.Max):
                    return True
        return False

    def _semantic_round_trip(
        self,
        parsed: exp.Expression,
        semantic_catalog: SemanticCatalog,
        warnings: list[str],
        errors: list[str],
    ) -> tuple[str, list[str]]:
        reasons: list[str] = []
        catalog_tables = {table.table_name.lower(): table for table in semantic_catalog.tables}
        alias_map = self._alias_map(parsed)
        query_tables = sorted({table.name for table in parsed.find_all(exp.Table)})

        missing_tables = [table for table in query_tables if table.lower() not in catalog_tables]
        if missing_tables:
            errors.append(f"Semantic catalog does not contain tables from the query: {', '.join(missing_tables)}.")
        elif query_tables:
            reasons.append("Все таблицы запроса найдены в semantic catalog.")

        fact_without_grain = [
            table.table_name
            for table_name in query_tables
            if (table := catalog_tables.get(table_name.lower())) is not None
            and table.table_role == "fact"
            and not str(table.grain or "").strip()
        ]
        if fact_without_grain:
            warnings.append(f"Fact-таблицы без grain в semantic catalog: {', '.join(sorted(set(fact_without_grain)))}.")
        elif any(
            (table := catalog_tables.get(table_name.lower())) is not None and table.table_role == "fact"
            for table_name in query_tables
        ):
            reasons.append("У fact-таблиц, участвующих в запросе, заполнен grain.")

        if len(query_tables) > 1:
            disconnected = self._disconnected_tables(query_tables, semantic_catalog)
            if disconnected:
                errors.append(
                    f"Semantic catalog has no join path covering: {', '.join(disconnected)}."
                )
            else:
                reasons.append("Для всех таблиц запроса найдены join path в semantic catalog.")

            invalid_join_pairs = self._invalid_join_pairs(parsed, alias_map, semantic_catalog)
            if invalid_join_pairs:
                details = ", ".join(sorted(f"{left}↔{right}" for left, right in invalid_join_pairs))
                errors.append(f"JOIN uses table pairs outside semantic relationships: {details}.")
            else:
                reasons.append("JOIN-предикаты опираются на связи semantic catalog.")

        invalid_filter_columns = self._columns_with_disabled_capability(
            parsed.find_all(exp.Where),
            alias_map,
            catalog_tables,
            capability="filterable",
        )
        if invalid_filter_columns:
            warnings.append(
                "Фильтры используют колонки без filterable=true: "
                + ", ".join(sorted(invalid_filter_columns))
                + "."
            )
        elif any(parsed.find_all(exp.Where)):
            reasons.append("Фильтры опираются на filterable-колонки.")

        invalid_group_columns = self._columns_with_disabled_capability(
            (group for select in parsed.find_all(exp.Select) for group in [select.args.get("group")] if group is not None),
            alias_map,
            catalog_tables,
            capability="groupable",
        )
        if invalid_group_columns:
            warnings.append(
                "Группировка использует колонки без groupable=true: "
                + ", ".join(sorted(invalid_group_columns))
                + "."
            )
        elif any(select.args.get("group") is not None for select in parsed.find_all(exp.Select)):
            reasons.append("Группировки опираются на groupable-колонки.")

        base_table = self._base_table(parsed, alias_map)
        if base_table:
            base_meta = catalog_tables.get(base_table.lower())
            if base_meta is not None and base_meta.table_role in {"lookup", "bridge"}:
                warnings.append(
                    f"Основная таблица `{base_table}` имеет роль `{base_meta.table_role}`. "
                    "Для агрегаций обычно нужна fact/event таблица."
                )

        score = 0
        checks = 0
        for passed in (
            not missing_tables,
            not fact_without_grain,
            len(query_tables) <= 1 or not self._disconnected_tables(query_tables, semantic_catalog),
            len(query_tables) <= 1 or not self._invalid_join_pairs(parsed, alias_map, semantic_catalog),
            not invalid_filter_columns and not invalid_group_columns,
        ):
            checks += 1
            if passed:
                score += 1

        if errors:
            return "low", reasons[:4]
        if score >= 4:
            return "high", reasons[:4]
        if score >= 2:
            return "medium", reasons[:4]
        return "low", reasons[:4]

    def _alias_map(self, parsed: exp.Expression) -> dict[str, str]:
        alias_map: dict[str, str] = {}
        for table in parsed.find_all(exp.Table):
            name = str(table.name or "")
            if not name:
                continue
            alias = str(getattr(table, "alias_or_name", None) or name)
            alias_map[name] = name
            alias_map[alias] = name
        return alias_map

    def _base_table(self, parsed: exp.Expression, alias_map: dict[str, str]) -> str | None:
        select = parsed if isinstance(parsed, exp.Select) else parsed.find(exp.Select)
        if select is None:
            return None
        from_expr = select.args.get("from")
        if from_expr is None:
            return None
        table = next(from_expr.find_all(exp.Table), None)
        if table is None:
            return None
        return alias_map.get(str(getattr(table, "alias_or_name", None) or table.name), str(table.name))

    def _disconnected_tables(
        self,
        query_tables: list[str],
        semantic_catalog: SemanticCatalog,
    ) -> list[str]:
        adjacency: dict[str, set[str]] = {}
        for relationship in semantic_catalog.relationships:
            left = relationship.from_table.lower()
            right = relationship.to_table.lower()
            adjacency.setdefault(left, set()).add(right)
            adjacency.setdefault(right, set()).add(left)

        if not query_tables:
            return []

        pending = [query_tables[0].lower()]
        visited = {query_tables[0].lower()}
        while pending:
            current = pending.pop(0)
            for neighbor in adjacency.get(current, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                pending.append(neighbor)

        return sorted(table for table in query_tables if table.lower() not in visited)

    def _invalid_join_pairs(
        self,
        parsed: exp.Expression,
        alias_map: dict[str, str],
        semantic_catalog: SemanticCatalog,
    ) -> set[tuple[str, str]]:
        known_pairs = {
            tuple(sorted((relationship.from_table, relationship.to_table)))
            for relationship in semantic_catalog.relationships
        }
        invalid_pairs: set[tuple[str, str]] = set()
        for select in parsed.find_all(exp.Select):
            for join in select.args.get("joins") or []:
                on_expr = join.args.get("on")
                if on_expr is None:
                    continue
                tables = {
                    alias_map.get(str(column.table), str(column.table))
                    for column in on_expr.find_all(exp.Column)
                    if getattr(column, "table", None)
                }
                if len(tables) != 2:
                    continue
                pair = tuple(sorted(tables))
                if pair not in known_pairs:
                    invalid_pairs.add(pair)
        return invalid_pairs

    def _columns_with_disabled_capability(
        self,
        expressions,
        alias_map: dict[str, str],
        catalog_tables: dict[str, Any],
        *,
        capability: str,
    ) -> set[str]:
        invalid: set[str] = set()
        for expression in expressions:
            if expression is None:
                continue
            for column in expression.find_all(exp.Column):
                resolved = self._resolve_catalog_column(column, alias_map, catalog_tables)
                if resolved is None:
                    continue
                table_name, column_meta = resolved
                if capability == "groupable" and "time_axis" in column_meta.analytics_roles:
                    continue
                if capability == "filterable" and column_meta.is_pk:
                    continue
                if not getattr(column_meta, capability):
                    invalid.add(f"{table_name}.{column_meta.column_name}")
        return invalid

    def _resolve_catalog_column(
        self,
        column: exp.Column,
        alias_map: dict[str, str],
        catalog_tables: dict[str, Any],
    ) -> tuple[str, SemanticColumn] | None:
        table_token = str(getattr(column, "table", None) or "").strip()
        column_name = str(getattr(column, "name", None) or "").strip()
        if not column_name:
            return None
        resolved_table = alias_map.get(table_token, table_token)
        table_meta = catalog_tables.get(resolved_table.lower())
        if table_meta is None:
            return None
        column_meta = next(
            (candidate for candidate in table_meta.columns if candidate.column_name.lower() == column_name.lower()),
            None,
        )
        if column_meta is None:
            return None
        return table_meta.table_name, column_meta

    def format_sql(self, sql: str, dialect: str) -> str:
        cleaned_sql = sql.strip().rstrip(";")
        if not cleaned_sql:
            return ""

        try:
            parsed = parse_one(cleaned_sql, read=self._read_dialect(dialect))
        except Exception:  # noqa: BLE001
            return cleaned_sql

        try:
            return parsed.sql(pretty=True, dialect=self._read_dialect(dialect))
        except Exception:  # noqa: BLE001
            return cleaned_sql

    def _apply_row_limit(self, parsed: exp.Expression, warnings: list[str]) -> exp.Expression:
        limit_clause = parsed.args.get("limit")
        if limit_clause is None:
            parsed.set("limit", exp.Limit(expression=exp.Literal.number(settings.default_row_limit)))
            warnings.append(f"LIMIT {settings.default_row_limit} was added automatically.")
            return parsed

        limit_value = self._extract_limit_value(limit_clause)
        if limit_value is not None and limit_value > settings.max_row_limit:
            parsed.set("limit", exp.Limit(expression=exp.Literal.number(settings.max_row_limit)))
            warnings.append(f"LIMIT {limit_value} was reduced to {settings.max_row_limit}.")
        return parsed

    def _extract_limit_value(self, limit_clause: exp.Expression) -> int | None:
        if not isinstance(limit_clause, exp.Limit):
            return None

        value = limit_clause.args.get("expression") or limit_clause.args.get("this")
        if not isinstance(value, exp.Literal) or value.is_string:
            return None

        try:
            return int(str(value.this))
        except ValueError:
            return None

    def _read_dialect(self, dialect: str) -> str:
        if dialect == "postgresql":
            return "postgres"
        return dialect
