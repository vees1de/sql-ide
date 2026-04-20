from __future__ import annotations

from sqlglot import expressions as exp
from sqlglot import parse, parse_one

from app.core.config import settings
from app.schemas.query import ValidationPayload


class SQLValidationAgent:
    def run(
        self,
        sql: str,
        dialect: str,
        allowed_tables: list[str] | tuple[str, ...] | None = None,
    ) -> ValidationPayload:
        errors: list[str] = []
        warnings: list[str] = []

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

        parsed = self._apply_row_limit(parsed, warnings)
        final_sql = self.format_sql(parsed.sql(pretty=True, dialect=self._read_dialect(dialect)), dialect)

        return ValidationPayload(
            valid=not errors,
            sql=final_sql,
            tables=tables,
            warnings=warnings,
            errors=errors,
        )

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
