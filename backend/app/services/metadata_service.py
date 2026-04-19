from __future__ import annotations

from sqlalchemy import inspect

from app.core.config import settings
from app.db.session import analytics_engine
from app.schemas.metadata import ColumnMetadata, SchemaMetadataResponse, TableMetadata


class MetadataService:
    def get_schema(self) -> SchemaMetadataResponse:
        inspector = inspect(analytics_engine)
        tables: list[TableMetadata] = []
        for table_name in inspector.get_table_names():
            columns = [
                ColumnMetadata(name=column["name"], type=str(column["type"]))
                for column in inspector.get_columns(table_name)
            ]
            tables.append(TableMetadata(name=table_name, columns=columns))

        return SchemaMetadataResponse(
            database_id=settings.demo_database_id,
            dialect=analytics_engine.dialect.name,
            tables=tables,
        )

    def list_table_names(self) -> list[str]:
        inspector = inspect(analytics_engine)
        return sorted(inspector.get_table_names())
