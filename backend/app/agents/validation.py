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
        effective_allowed_tables = tuple(allowed_tables or settings.allowed_tables)
        unknown_tables = sorted(set(tables) - set(effective_allowed_tables))
        if effective_allowed_tables and unknown_tables:
            errors.append(f"Query references tables outside the whitelist: {', '.join(unknown_tables)}.")

        final_sql = sql.strip().rstrip(";")
        if " limit " not in f" {final_sql.lower()} ":
            final_sql = f"{final_sql}\nLIMIT {settings.default_row_limit}"
            warnings.append(f"LIMIT {settings.default_row_limit} was added automatically.")

        return ValidationPayload(
            valid=not errors,
            sql=final_sql,
            tables=tables,
            warnings=warnings,
            errors=errors,
        )

    def _read_dialect(self, dialect: str) -> str:
        if dialect == "postgresql":
            return "postgres"
        return dialect
