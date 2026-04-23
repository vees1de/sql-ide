from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ColumnMetadata(BaseModel):
    name: str
    type: str
    nullable: bool = True
    is_pk: bool = False
    is_fk: bool = False
    referenced_table: str | None = None
    referenced_column: str | None = None
    # Optional observed value range — populated for date/numeric columns
    # so the LLM knows what data actually exists (prevents "last 30 days"
    # filters on snapshot tables from 2016).
    min_value: str | None = None
    max_value: str | None = None
    # Human-readable description from the knowledge layer (manual or auto).
    description: str | None = None
    example_values: list[Any] = Field(default_factory=list)


class RelationshipMetadata(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relation_type: str = "foreign_key"
    cardinality: str | None = None
    description: str | None = None


class AllowedJoinMetadata(BaseModel):
    from_table: str
    to_table: str
    via: str
    reason: str | None = None


class RelationshipGraphEdge(BaseModel):
    from_table: str
    to_table: str
    on: str


class TableMetadata(BaseModel):
    name: str
    schema_name: str | None = None
    columns: list[ColumnMetadata] = Field(default_factory=list)
    description: str | None = None
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    allowed_joins: list[AllowedJoinMetadata] = Field(default_factory=list)


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
