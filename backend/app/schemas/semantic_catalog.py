from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.metadata import RelationshipGraphEdge, SchemaMetadataResponse


SemanticType = Literal[
    "id",
    "foreign_key",
    "metric",
    "dimension",
    "datetime",
    "category",
    "name",
    "status",
    "boolean_flag",
    "currency",
    "countable_entity",
    "text",
    "location",
    "ratio",
    "duration",
]

TableRole = Literal["fact", "dimension", "bridge", "lookup", "event", "snapshot"]
AnalyticsRole = Literal["primary_metric", "supporting_metric", "default_filter", "default_group_by", "time_axis", "display_name"]
AggregationName = Literal["sum", "avg", "min", "max", "count", "count_distinct"]


class ColumnProfile(BaseModel):
    distinct_count: int | None = None
    null_ratio: float | None = None
    min_value: str | None = None
    max_value: str | None = None
    avg_length: float | None = None
    top_values: list[Any] = Field(default_factory=list)
    uniqueness_ratio: float | None = None
    numeric_mean: float | None = None
    numeric_min: float | None = None
    numeric_max: float | None = None


class SemanticColumn(BaseModel):
    schema_name: str
    table_name: str
    column_name: str
    label: str
    business_description: str
    semantic_types: list[SemanticType] = Field(default_factory=list)
    analytics_roles: list[AnalyticsRole] = Field(default_factory=list)
    value_type: str | None = None
    aggregation: list[AggregationName] = Field(default_factory=list)
    filterable: bool = True
    groupable: bool = False
    sortable: bool = True
    synonyms: list[str] = Field(default_factory=list)
    example_values: list[Any] = Field(default_factory=list)
    data_type: str = ""
    nullable: bool = True
    default_value: str | None = None
    max_length: int | None = None
    ordinal_position: int = 0
    is_pk: bool = False
    is_fk: bool = False
    referenced_table: str | None = None
    referenced_column: str | None = None
    comment: str | None = None
    profile: ColumnProfile = Field(default_factory=ColumnProfile)


class SemanticRelationship(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relationship_type: Literal["one-to-one", "one-to-many", "many-to-one", "bridge", "junction"]
    join_type: Literal["inner", "left"] = "inner"
    business_meaning: str
    join_priority: Literal["high", "medium", "low"] = "medium"
    confidence: float = 0.0
    path_id: str | None = None


class SemanticJoinPath(BaseModel):
    path_id: str
    from_table: str
    to_table: str
    joins: list[str] = Field(default_factory=list)
    business_use_case: str
    tables: list[str] = Field(default_factory=list)


class SemanticTable(BaseModel):
    schema_name: str
    table_name: str
    label: str
    business_description: str
    table_role: TableRole
    grain: str | None = None
    main_date_column: str | None = None
    main_entity: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    important_metrics: list[str] = Field(default_factory=list)
    important_dimensions: list[str] = Field(default_factory=list)
    row_count_estimate: int | None = None
    primary_key: list[str] = Field(default_factory=list)
    foreign_keys: list[SemanticRelationship] = Field(default_factory=list)
    indexes: list[dict[str, Any]] = Field(default_factory=list)
    comment: str | None = None
    columns: list[SemanticColumn] = Field(default_factory=list)
    relationships: list[SemanticRelationship] = Field(default_factory=list)
    join_paths: list[SemanticJoinPath] = Field(default_factory=list)


class SemanticCatalog(BaseModel):
    database_id: str
    dialect: str
    tables: list[SemanticTable] = Field(default_factory=list)
    relationships: list[SemanticRelationship] = Field(default_factory=list)
    join_paths: list[SemanticJoinPath] = Field(default_factory=list)
    relationship_graph: list[RelationshipGraphEdge] = Field(default_factory=list)


class SemanticRetrievalContext(BaseModel):
    catalog: SemanticCatalog
    schema: SchemaMetadataResponse
    dictionary_entries: list[dict[str, Any]] = Field(default_factory=list)
    table_names: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SemanticColumnEnrichment(BaseModel):
    column_name: str
    label: str | None = None
    business_description: str | None = None
    semantic_types: list[SemanticType] = Field(default_factory=list)
    analytics_roles: list[AnalyticsRole] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)


class SemanticTableEnrichment(BaseModel):
    table_name: str
    label: str | None = None
    business_description: str | None = None
    table_role: TableRole | None = None
    grain: str | None = None
    main_date_column: str | None = None
    main_entity: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    important_metrics: list[str] = Field(default_factory=list)
    important_dimensions: list[str] = Field(default_factory=list)
    columns: list[SemanticColumnEnrichment] = Field(default_factory=list)


class SemanticCatalogActivationRequest(BaseModel):
    database_id: str
    refresh: bool = False
    database_description: str | None = None


class SemanticTablePatch(BaseModel):
    label: str | None = None
    business_description: str | None = None
    table_role: TableRole | None = None
    grain: str | None = None
    main_date_column: str | None = None
    main_entity: str | None = None
    synonyms: list[str] | None = None
    important_metrics: list[str] | None = None
    important_dimensions: list[str] | None = None


class SemanticColumnPatch(BaseModel):
    label: str | None = None
    business_description: str | None = None
    semantic_types: list[SemanticType] | None = None
    analytics_roles: list[AnalyticsRole] | None = None
    synonyms: list[str] | None = None
    groupable: bool | None = None
    filterable: bool | None = None
