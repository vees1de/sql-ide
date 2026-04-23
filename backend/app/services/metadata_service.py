from __future__ import annotations

from sqlalchemy import inspect

from app.core.config import settings
from app.db.session import analytics_engine
from app.schemas.metadata import ColumnMetadata, RelationshipMetadata, SchemaMetadataResponse, TableMetadata
from app.services.relationship_graph import build_relationship_graph


class MetadataService:
    def get_schema(self) -> SchemaMetadataResponse:
        inspector = inspect(analytics_engine)
        tables: list[TableMetadata] = []
        table_names = inspector.get_table_names()
        relationships: list[RelationshipMetadata] = []

        for table_name in table_names:
            columns = [
                ColumnMetadata(name=column["name"], type=str(column["type"]))
                for column in inspector.get_columns(table_name)
            ]
            tables.append(TableMetadata(name=table_name, columns=columns))

        table_name_set = set(table_names)
        for table_name in table_names:
            for foreign_key in inspector.get_foreign_keys(table_name):
                referred_table = foreign_key.get("referred_table")
                if not referred_table or referred_table not in table_name_set:
                    continue
                from_columns = [str(column) for column in foreign_key.get("constrained_columns") or [] if column]
                to_columns = [str(column) for column in foreign_key.get("referred_columns") or [] if column]
                for from_column, to_column in zip(from_columns, to_columns):
                    relationships.append(
                        RelationshipMetadata(
                            from_table=table_name,
                            from_column=from_column,
                            to_table=str(referred_table),
                            to_column=to_column,
                            cardinality="many_to_one",
                        )
                    )

        relationship_graph = build_relationship_graph(relationships)
        return SchemaMetadataResponse(
            database_id=settings.analytics_database_id,
            dialect=analytics_engine.dialect.name,
            tables=tables,
            relationships=relationships,
            relationship_graph=relationship_graph,
        )

    def list_table_names(self) -> list[str]:
        inspector = inspect(analytics_engine)
        return sorted(inspector.get_table_names())
