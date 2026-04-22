from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.metadata import SchemaMetadataResponse, TableMetadata
from app.schemas.semantic_catalog import SemanticCatalog, SemanticTable
from app.services.database_resolution import resolve_dialect, resolve_engine
from app.services.schema_context_provider import SchemaContextProvider
from app.services.semantic_catalog_service import SemanticCatalogService


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


@dataclass
class LLMSchemaReconToolbox:
    db: Session
    database_id: str
    schema_provider: SchemaContextProvider = field(default_factory=SchemaContextProvider)
    semantic_catalog_service: SemanticCatalogService = field(default_factory=SemanticCatalogService)
    _schema: SchemaMetadataResponse | None = None
    _catalog: SemanticCatalog | None = None

    TOOL_ROW_CAP: int = 5
    TOOL_VALUE_CAP: int = 12
    TOOL_TABLE_CAP: int = 12

    def tool_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "list_tables",
                    "description": "List the most relevant tables for the current analytics request. Use this first when you need to orient yourself in the schema.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query_hint": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "describe_table",
                    "description": "Describe one table: business meaning, columns, direct relationships, and example values from the semantic catalog.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {"type": "string"},
                        },
                        "required": ["table_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "sample_rows",
                    "description": "Fetch a tiny read-only sample of rows from a table to inspect real values and event semantics. Limit is capped server-side.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {"type": "string"},
                            "columns": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "limit": {"type": "integer"},
                        },
                        "required": ["table_name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "distinct_values",
                    "description": "Fetch top distinct values and counts for a column. Use for statuses, ratings, categories, store ids, and other low-cardinality fields before guessing enum values.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "table_name": {"type": "string"},
                            "column_name": {"type": "string"},
                            "limit": {"type": "integer"},
                        },
                        "required": ["table_name", "column_name"],
                    },
                },
            },
        ]

    def execute_tool(self, name: str, arguments: str | dict[str, Any] | None) -> dict[str, Any]:
        parsed_arguments: dict[str, Any]
        if isinstance(arguments, str):
            try:
                parsed_arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                parsed_arguments = {}
        elif isinstance(arguments, dict):
            parsed_arguments = dict(arguments)
        else:
            parsed_arguments = {}

        handlers = {
            "list_tables": self.list_tables,
            "describe_table": self.describe_table,
            "sample_rows": self.sample_rows,
            "distinct_values": self.distinct_values,
        }
        handler = handlers.get(name)
        if handler is None:
            return {"error": f"Unknown tool `{name}`."}
        try:
            return handler(**parsed_arguments)
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc), "tool": name, "arguments": parsed_arguments}

    def list_tables(self, query_hint: str | None = None, limit: int | None = None) -> dict[str, Any]:
        actual_limit = max(1, min(int(limit or self.TOOL_TABLE_CAP), self.TOOL_TABLE_CAP))
        catalog = self._load_catalog()
        scored_tables: list[tuple[float, SemanticTable]] = []
        for table in catalog.tables:
            haystack = " ".join(
                [
                    table.table_name,
                    table.label,
                    table.business_description,
                    " ".join(table.synonyms),
                    " ".join(table.important_metrics),
                    " ".join(table.important_dimensions),
                ]
            ).lower()
            score = 0.0
            if query_hint:
                for token in self._tokenize(query_hint):
                    if token in haystack:
                        score += 1.0
            scored_tables.append((score, table))

        scored_tables.sort(key=lambda item: (item[0], item[1].table_name), reverse=True)
        selected = [table for _score, table in scored_tables[:actual_limit]]
        return {
            "tables": [
                {
                    "table_name": table.table_name,
                    "label": table.label,
                    "business_description": table.business_description,
                    "table_role": table.table_role,
                    "grain": table.grain,
                    "important_metrics": list(table.important_metrics[:6]),
                    "important_dimensions": list(table.important_dimensions[:8]),
                }
                for table in selected
            ],
            "count": len(selected),
        }

    def describe_table(self, table_name: str) -> dict[str, Any]:
        table = self._resolve_table(table_name)
        direct_relationships = [
            relationship
            for relationship in self._load_catalog().relationships
            if relationship.from_table == table.table_name or relationship.to_table == table.table_name
        ]
        return {
            "table_name": table.table_name,
            "schema_name": table.schema_name,
            "label": table.label,
            "business_description": table.business_description,
            "table_role": table.table_role,
            "grain": table.grain,
            "main_date_column": table.main_date_column,
            "main_entity": table.main_entity,
            "important_metrics": list(table.important_metrics),
            "important_dimensions": list(table.important_dimensions),
            "columns": [
                {
                    "column_name": column.column_name,
                    "label": column.label,
                    "business_description": column.business_description,
                    "data_type": column.data_type,
                    "semantic_types": list(column.semantic_types),
                    "analytics_roles": list(column.analytics_roles),
                    "example_values": [_json_safe(value) for value in list(column.example_values[:5])],
                    "nullable": column.nullable,
                    "is_pk": column.is_pk,
                    "is_fk": column.is_fk,
                    "referenced_table": column.referenced_table,
                    "referenced_column": column.referenced_column,
                }
                for column in table.columns
            ],
            "relationships": [
                {
                    "from_table": relationship.from_table,
                    "from_column": relationship.from_column,
                    "to_table": relationship.to_table,
                    "to_column": relationship.to_column,
                    "relationship_type": relationship.relationship_type,
                    "business_meaning": relationship.business_meaning,
                }
                for relationship in direct_relationships
            ],
        }

    def sample_rows(
        self,
        table_name: str,
        columns: list[str] | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        table = self._resolve_table(table_name)
        selected_columns = self._resolve_sample_columns(table, columns)
        actual_limit = max(1, min(int(limit or self.TOOL_ROW_CAP), self.TOOL_ROW_CAP))
        schema_prefix = f"{_quote_identifier(table.schema_name)}." if table.schema_name else ""
        select_list = ", ".join(_quote_identifier(column) for column in selected_columns)
        sql = f"SELECT {select_list} FROM {schema_prefix}{_quote_identifier(table.table_name)} LIMIT {actual_limit}"
        rows = self._run_query(sql)
        return {
            "table_name": table.table_name,
            "columns": selected_columns,
            "rows": rows,
            "limit": actual_limit,
        }

    def distinct_values(self, table_name: str, column_name: str, limit: int | None = None) -> dict[str, Any]:
        table = self._resolve_table(table_name)
        actual_limit = max(1, min(int(limit or self.TOOL_VALUE_CAP), self.TOOL_VALUE_CAP))
        column = next((item for item in table.columns if item.column_name == column_name), None)
        if column is None:
            raise ValueError(f"Unknown column `{column_name}` in table `{table.table_name}`.")

        schema_prefix = f"{_quote_identifier(table.schema_name)}." if table.schema_name else ""
        quoted_column = _quote_identifier(column_name)
        sql = (
            f"SELECT {quoted_column} AS value, COUNT(*) AS row_count "
            f"FROM {schema_prefix}{_quote_identifier(table.table_name)} "
            f"WHERE {quoted_column} IS NOT NULL "
            f"GROUP BY 1 "
            f"ORDER BY row_count DESC, value ASC "
            f"LIMIT {actual_limit}"
        )
        rows = self._run_query(sql)
        return {
            "table_name": table.table_name,
            "column_name": column_name,
            "values": rows,
            "limit": actual_limit,
        }

    def _load_schema(self) -> SchemaMetadataResponse:
        if self._schema is None:
            self._schema = self.schema_provider.get_schema_for_llm(self.db, self.database_id)
        return self._schema

    def _load_catalog(self) -> SemanticCatalog:
        if self._catalog is None:
            cached = self.semantic_catalog_service.load_catalog(self.db, self.database_id)
            self._catalog = cached or self.semantic_catalog_service.get_catalog(self.db, self.database_id)
        return self._catalog

    def _resolve_table(self, table_name: str) -> SemanticTable:
        normalized = str(table_name or "").strip().lower()
        if not normalized:
            raise ValueError("table_name is required.")
        catalog = self._load_catalog()
        for table in catalog.tables:
            if table.table_name.lower() == normalized:
                return table
        schema = self._load_schema()
        for table in schema.tables:
            if table.name.lower() == normalized:
                return SemanticTable(
                    schema_name="public",
                    table_name=table.name,
                    label=table.name,
                    business_description="",
                    table_role="dimension",
                    columns=[],
                )
        raise ValueError(f"Unknown table `{table_name}`.")

    def _resolve_sample_columns(self, table: SemanticTable, requested_columns: list[str] | None) -> list[str]:
        available = [column.column_name for column in table.columns]
        if not available:
            schema_table = next(
                (item for item in self._load_schema().tables if item.name == table.table_name),
                None,
            )
            available = [column.name for column in (schema_table.columns if schema_table else [])]
        if requested_columns:
            selected = [column for column in requested_columns if column in set(available)]
            if selected:
                return selected[:8]
        priority = [
            column.column_name
            for column in table.columns
            if "time_axis" in column.analytics_roles
            or "status" in column.semantic_types
            or "id" in column.semantic_types
            or "metric" in column.semantic_types
        ]
        ordered = list(dict.fromkeys([*priority, *available]))
        return ordered[:8]

    def _run_query(self, sql: str) -> list[dict[str, Any]]:
        dialect = resolve_dialect(self.db, self.database_id)
        engine = resolve_engine(self.db, self.database_id)
        with engine.begin() as connection:
            self._apply_read_only_guards(connection, dialect)
            result = connection.execute(text(sql))
            return [
                {key: _json_safe(value) for key, value in row.items()}
                for row in result.mappings().all()
            ]

    def _apply_read_only_guards(self, connection: Any, dialect: str) -> None:
        if dialect.startswith("postgres"):
            timeout_ms = min(max(settings.query_timeout_seconds * 1000, 1000), 5000)
            connection.exec_driver_sql("SET LOCAL default_transaction_read_only = on")
            connection.exec_driver_sql(f"SET LOCAL statement_timeout = {timeout_ms}")
            return
        if dialect.startswith("mysql") or dialect.startswith("mariadb"):
            connection.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
            return
        if dialect.startswith("sqlite"):
            connection.exec_driver_sql("PRAGMA query_only = ON")
            return

    def _tokenize(self, text: str) -> list[str]:
        return [token for token in str(text).lower().replace("_", " ").split() if token]


class LLMSchemaReconService:
    def build_toolbox(self, db: Session, database_id: str) -> LLMSchemaReconToolbox:
        return LLMSchemaReconToolbox(db=db, database_id=database_id)
