from __future__ import annotations

from pydantic import BaseModel, Field


class ColumnMetadata(BaseModel):
    name: str
    type: str


class TableMetadata(BaseModel):
    name: str
    columns: list[ColumnMetadata] = Field(default_factory=list)


class SchemaMetadataResponse(BaseModel):
    database_id: str
    dialect: str
    tables: list[TableMetadata] = Field(default_factory=list)
