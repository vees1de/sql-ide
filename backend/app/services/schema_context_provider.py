from __future__ import annotations

from typing import Any

from sqlalchemy import inspect as sa_inspect, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import analytics_engine
from app.schemas.metadata import (
    AllowedJoinMetadata,
    ColumnMetadata,
    RelationshipMetadata,
    SchemaMetadataResponse,
    TableMetadata,
)
from app.services.database_resolution import resolve_allowed_tables, resolve_dialect, resolve_engine
from app.services.knowledge_service import KnowledgeService
from app.services.relationship_graph import build_relationship_graph


SchemaContext = SchemaMetadataResponse


class SchemaContextProvider:
    SAMPLE_ROW_LIMIT = 3

    def __init__(self) -> None:
        self.knowledge_service = KnowledgeService()

    def get_schema_for_llm(self, db: Session, database_connection_id: str) -> SchemaContext:
        knowledge_schema = self._schema_from_knowledge(db, database_connection_id)
        if knowledge_schema is not None and knowledge_schema.tables:
            return self._with_allowed_joins(knowledge_schema)
        return self._with_allowed_joins(self._schema_from_live_introspection(db, database_connection_id))

    def list_tables(self, db: Session, database_connection_id: str) -> list[TableMetadata]:
        return list(self.get_schema_for_llm(db, database_connection_id).tables)

    def describe_table(self, db: Session, database_connection_id: str, table_name: str) -> TableMetadata | None:
        normalized = str(table_name or "").strip().lower()
        if not normalized:
            return None
        for table in self.get_schema_for_llm(db, database_connection_id).tables:
            if table.name.lower() == normalized:
                return table
        return None

    def list_columns(self, db: Session, database_connection_id: str, table_name: str) -> list[ColumnMetadata]:
        table = self.describe_table(db, database_connection_id, table_name)
        return list(table.columns) if table is not None else []

    def sample_rows(self, db: Session, database_connection_id: str, table_name: str, limit: int | None = None) -> list[dict[str, Any]]:
        table = self.describe_table(db, database_connection_id, table_name)
        if table is None:
            return []
        try:
            engine = resolve_engine(db, database_connection_id)
        except Exception:  # noqa: BLE001
            return list(table.sample_rows)
        selected_columns = [column.name for column in table.columns[:6]]
        return self._sample_rows(
            engine,
            table.schema_name or "public",
            table.name,
            selected_columns,
            limit=limit or self.SAMPLE_ROW_LIMIT,
        )

    def _schema_from_knowledge(self, db: Session, database_connection_id: str) -> SchemaContext | None:
        try:
            summary = self.knowledge_service.get_summary(db, database_connection_id)
        except Exception:  # noqa: BLE001
            return None

        tables: list[TableMetadata] = []
        relationships: list[RelationshipMetadata] = []
        for table in summary.tables:
            try:
                table_model = self.knowledge_service.get_table_by_key(
                    db,
                    database_connection_id,
                    table.schema_name,
                    table.table_name,
                )
            except Exception:  # noqa: BLE001
                continue
            if table_model is None:
                continue

            engine = None
            try:
                from app.services.database_resolution import resolve_engine
                engine = resolve_engine(db, database_connection_id)
            except Exception:  # noqa: BLE001
                pass

            columns: list[ColumnMetadata] = []
            primary_key = set(getattr(table_model, "primary_key", []) or [])
            prefetched_relationships = getattr(table_model, "_prefetched_relationships", [])
            for column in table_model.columns:
                if column.status != "active" or column.hidden_for_llm:
                    continue
                min_val: str | None = None
                max_val: str | None = None
                if engine is not None:
                    min_val, max_val = self._sample_value_range(
                        engine, table.table_name, column.column_name, column.data_type
                    )
                col_desc = column.description_manual or None
                columns.append(ColumnMetadata(
                    name=column.column_name,
                    type=column.data_type,
                    nullable=bool(column.is_nullable),
                    is_pk=column.column_name in primary_key,
                    is_fk=any(
                        relationship.from_column_name == column.column_name or relationship.to_column_name == column.column_name
                        for relationship in prefetched_relationships
                    ),
                    referenced_table=next(
                        (
                            relationship.to_table_name
                            for relationship in prefetched_relationships
                            if relationship.from_column_name == column.column_name
                        ),
                        None,
                    ),
                    referenced_column=next(
                        (
                            relationship.to_column_name
                            for relationship in prefetched_relationships
                            if relationship.from_column_name == column.column_name
                        ),
                        None,
                    ),
                    min_value=min_val,
                    max_value=max_val,
                    description=col_desc,
                    example_values=list(column.sample_values or [])[:5],
                ))

            table_desc = table_model.description_manual or None
            if columns:
                sample_rows = []
                if engine is not None:
                    sample_rows = self._sample_rows(
                        engine,
                        table.schema_name,
                        table.table_name,
                        [column.name for column in columns[:6]],
                    )
                tables.append(TableMetadata(
                    name=table.table_name,
                    schema_name=table.schema_name,
                    columns=columns,
                    description=table_desc,
                    sample_rows=sample_rows,
                ))

            for relationship in prefetched_relationships:
                if relationship.status != "active" or relationship.is_disabled:
                    continue
                relationships.append(
                    RelationshipMetadata(
                        from_table=relationship.from_table_name,
                        from_column=relationship.from_column_name,
                        to_table=relationship.to_table_name,
                        to_column=relationship.to_column_name,
                        relation_type=relationship.relation_type,
                        cardinality=relationship.cardinality,
                        description=relationship.description_manual,
                    )
                )

        if not tables:
            return None

        relationship_graph = build_relationship_graph(list(relationships))
        return SchemaMetadataResponse(
            database_id=summary.database_id,
            dialect=summary.dialect,
            tables=tables,
            relationships=list(
                {
                    (
                        relationship.from_table,
                        relationship.from_column,
                        relationship.to_table,
                        relationship.to_column,
                        relationship.relation_type,
                        relationship.cardinality,
                    ): relationship
                    for relationship in relationships
                }.values()
            ),
            relationship_graph=relationship_graph,
        )

    # ------------------------------------------------------------------
    # Value-range sampling: only for columns that look like dates/years.
    # Helps the LLM anchor "last 30 days" / "recent" filters to data reality.
    # ------------------------------------------------------------------
    _DATE_NAME_HINTS = ("date", "year", "period", "season", "time", "created", "updated", "timestamp")
    _DATE_TYPE_HINTS = ("date", "timestamp", "time")

    @staticmethod
    def _looks_like_date_column(col_name: str, col_type: str) -> bool:
        name_lower = col_name.lower()
        type_lower = col_type.lower()
        if any(kw in type_lower for kw in SchemaContextProvider._DATE_TYPE_HINTS):
            return True
        return any(kw in name_lower for kw in SchemaContextProvider._DATE_NAME_HINTS)

    @classmethod
    def _sample_value_range(
        cls, engine, table_name: str, col_name: str, col_type: str
    ) -> tuple[str | None, str | None]:
        if not cls._looks_like_date_column(col_name, col_type):
            return None, None
        try:
            # Quote identifiers to preserve case sensitivity across dialects.
            query = text(f'SELECT MIN("{col_name}") AS mn, MAX("{col_name}") AS mx FROM "{table_name}"')
            with engine.connect() as conn:
                row = conn.execute(query).first()
            if row is None:
                return None, None
            mn = row[0]
            mx = row[1]
            to_str = lambda v: None if v is None else str(v)
            return to_str(mn), to_str(mx)
        except Exception:  # noqa: BLE001
            return None, None

    def _schema_from_live_introspection(self, db: Session, database_connection_id: str) -> SchemaContext:
        dialect = resolve_dialect(db, database_connection_id)
        engine = resolve_engine(db, database_connection_id)
        allowed_tables = set(resolve_allowed_tables(db, database_connection_id, engine))
        inspector = sa_inspect(engine)

        try:
            if dialect.startswith("postgres"):
                table_names = inspector.get_table_names(schema="public")
            else:
                table_names = inspector.get_table_names()
        except Exception:  # noqa: BLE001
            table_names = []

        tables: list[TableMetadata] = []
        relationships: list[RelationshipMetadata] = []
        for table_name in sorted(table_names):
            if allowed_tables and table_name not in allowed_tables:
                continue
            foreign_keys: list[dict[str, Any]] = []
            try:
                raw_columns = list(inspector.get_columns(table_name))
                pk_columns = set((inspector.get_pk_constraint(table_name) or {}).get("constrained_columns") or [])
                foreign_keys = list(inspector.get_foreign_keys(table_name))
                fk_map = {
                    str(column_name): (str(foreign_key.get("referred_table") or ""), str((foreign_key.get("referred_columns") or [None])[0]))
                    for foreign_key in foreign_keys
                    for column_name in (foreign_key.get("constrained_columns") or [])
                    if column_name
                }
                columns: list[ColumnMetadata] = []
                for column in raw_columns:
                    col_name = str(column["name"])
                    col_type = str(column["type"])
                    min_val, max_val = self._sample_value_range(engine, table_name, col_name, col_type)
                    columns.append(ColumnMetadata(
                        name=col_name,
                        type=col_type,
                        nullable=bool(column.get("nullable", True)),
                        is_pk=col_name in pk_columns,
                        is_fk=col_name in fk_map,
                        referenced_table=fk_map.get(col_name, (None, None))[0],
                        referenced_column=fk_map.get(col_name, (None, None))[1],
                        min_value=min_val,
                        max_value=max_val,
                    ))
            except Exception:  # noqa: BLE001
                columns = []
            if columns:
                sample_rows = self._sample_rows(
                    engine,
                    "public" if dialect.startswith("postgres") else None,
                    str(table_name),
                    [column.name for column in columns[:6]],
                )
                tables.append(
                    TableMetadata(
                        name=str(table_name),
                        schema_name="public" if dialect.startswith("postgres") else None,
                        columns=columns,
                        sample_rows=sample_rows,
                    )
                )
            try:
                for foreign_key in foreign_keys:
                    referred_table = foreign_key.get("referred_table")
                    if not referred_table:
                        continue
                    if allowed_tables and referred_table not in allowed_tables:
                        continue
                    from_columns = [str(column) for column in foreign_key.get("constrained_columns") or [] if column]
                    to_columns = [str(column) for column in foreign_key.get("referred_columns") or [] if column]
                    for from_column, to_column in zip(from_columns, to_columns):
                        relationships.append(
                            RelationshipMetadata(
                                from_table=str(table_name),
                                from_column=from_column,
                                to_table=str(referred_table),
                                to_column=to_column,
                                cardinality="many_to_one",
                            )
                        )
            except Exception:  # noqa: BLE001
                pass

        return SchemaMetadataResponse(
            database_id=database_connection_id,
            dialect=dialect or analytics_engine.dialect.name,
            tables=tables,
            relationships=list(
                {
                    (
                        relationship.from_table,
                        relationship.from_column,
                        relationship.to_table,
                        relationship.to_column,
                        relationship.relation_type,
                        relationship.cardinality,
                    ): relationship
                    for relationship in relationships
                }.values()
            ),
            relationship_graph=build_relationship_graph(relationships),
        )

    def _with_allowed_joins(self, schema: SchemaContext) -> SchemaContext:
        relationship_map: dict[str, list[AllowedJoinMetadata]] = {}
        for relationship in schema.relationships:
            relationship_map.setdefault(relationship.from_table, []).append(
                AllowedJoinMetadata(
                    from_table=relationship.from_table,
                    to_table=relationship.to_table,
                    via=f"{relationship.from_table}.{relationship.from_column} = {relationship.to_table}.{relationship.to_column}",
                    reason=relationship.description,
                )
            )
            relationship_map.setdefault(relationship.to_table, []).append(
                AllowedJoinMetadata(
                    from_table=relationship.to_table,
                    to_table=relationship.from_table,
                    via=f"{relationship.to_table}.{relationship.to_column} = {relationship.from_table}.{relationship.from_column}",
                    reason=relationship.description,
                )
            )

        enriched_tables = [
            table.model_copy(update={"allowed_joins": relationship_map.get(table.name, [])})
            for table in schema.tables
        ]
        return schema.model_copy(update={"tables": enriched_tables})

    def _sample_rows(
        self,
        engine,
        schema_name: str | None,
        table_name: str,
        columns: list[str],
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        if not columns:
            return []
        actual_limit = max(1, min(int(limit or self.SAMPLE_ROW_LIMIT), 5))
        try:
            schema_prefix = f'"{schema_name}".' if schema_name else ""
            select_list = ", ".join(f'"{column}"' for column in columns)
            query = text(
                f'SELECT {select_list} FROM {schema_prefix}"{table_name}" LIMIT {actual_limit}'
            )
            with engine.connect() as conn:
                rows = conn.execute(query).mappings().all()
            return [{key: value for key, value in row.items()} for row in rows]
        except Exception:  # noqa: BLE001
            return []
