from __future__ import annotations

from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import analytics_engine
from app.schemas.metadata import ColumnMetadata, RelationshipMetadata, SchemaMetadataResponse, TableMetadata
from app.services.database_resolution import resolve_allowed_tables, resolve_dialect, resolve_engine
from app.services.knowledge_service import KnowledgeService
from app.services.relationship_graph import build_relationship_graph


SchemaContext = SchemaMetadataResponse


class SchemaContextProvider:
    def __init__(self) -> None:
        self.knowledge_service = KnowledgeService()

    def get_schema_for_llm(self, db: Session, database_connection_id: str) -> SchemaContext:
        knowledge_schema = self._schema_from_knowledge(db, database_connection_id)
        if knowledge_schema is not None and knowledge_schema.tables:
            return knowledge_schema
        return self._schema_from_live_introspection(db, database_connection_id)

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

            columns: list[ColumnMetadata] = []
            for column in table_model.columns:
                if column.status != "active" or column.hidden_for_llm:
                    continue
                columns.append(ColumnMetadata(name=column.column_name, type=column.data_type))

            if columns:
                tables.append(TableMetadata(name=table.table_name, columns=columns))

            prefetched_relationships = getattr(table_model, "_prefetched_relationships", [])
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
            try:
                columns = [
                    ColumnMetadata(name=str(column["name"]), type=str(column["type"]))
                    for column in inspector.get_columns(table_name)
                ]
            except Exception:  # noqa: BLE001
                columns = []
            if columns:
                tables.append(TableMetadata(name=str(table_name), columns=columns))
            try:
                for foreign_key in inspector.get_foreign_keys(table_name):
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
