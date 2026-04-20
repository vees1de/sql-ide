from __future__ import annotations

from pydantic import BaseModel, Field


class ColumnMetadata(BaseModel):
    name: str
    type: str


class RelationshipMetadata(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relation_type: str = "foreign_key"
    cardinality: str | None = None


class TableMetadata(BaseModel):
    name: str
    columns: list[ColumnMetadata] = Field(default_factory=list)


class SchemaMetadataResponse(BaseModel):
    database_id: str
    dialect: str
    tables: list[TableMetadata] = Field(default_factory=list)
    relationships: list[RelationshipMetadata] = Field(default_factory=list)
