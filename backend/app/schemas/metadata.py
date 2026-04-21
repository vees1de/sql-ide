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


class RelationshipGraphEdge(BaseModel):
    from_table: str
    to_table: str
    on: str


class TableMetadata(BaseModel):
    name: str
    columns: list[ColumnMetadata] = Field(default_factory=list)


class SchemaMetadataResponse(BaseModel):
    database_id: str
    dialect: str
    tables: list[TableMetadata] = Field(default_factory=list)
    relationships: list[RelationshipMetadata] = Field(default_factory=list)
    relationship_graph: list[RelationshipGraphEdge] = Field(default_factory=list)


class LLMModelAliasItem(BaseModel):
    alias: str
    model: str


class LLMModelAliasesResponse(BaseModel):
    aliases: list[LLMModelAliasItem] = Field(default_factory=list)
    default_alias: str
    current_alias: str
