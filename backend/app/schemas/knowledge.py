from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dictionary import DictionaryEntryRead


class KnowledgeScanRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    database_id: str
    database_label: str
    dialect: str
    scan_type: str
    status: str
    stage: str
    summary: dict = Field(default_factory=dict)
    error_message: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class KnowledgeColumnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    database_id: str
    table_id: str
    schema_name: str
    table_name: str
    column_name: str
    data_type: str
    ordinal_position: int
    is_nullable: bool
    default_value: str | None = None
    status: str
    distinct_count: int | None = None
    null_ratio: float | None = None
    min_value: str | None = None
    max_value: str | None = None
    sample_values: list[str] = Field(default_factory=list)
    semantic_label_auto: str | None = None
    semantic_label_manual: str | None = None
    description_auto: str | None = None
    description_manual: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    sensitivity: str | None = None
    hidden_for_llm: bool = False


class KnowledgeRelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    database_id: str
    from_schema_name: str
    from_table_name: str
    from_column_name: str
    to_schema_name: str
    to_table_name: str
    to_column_name: str
    relation_type: str
    cardinality: str | None = None
    confidence: float
    approved: bool
    is_disabled: bool = False
    description_manual: str | None = None
    status: str


class KnowledgeTableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    database_id: str
    schema_name: str
    table_name: str
    object_type: str
    status: str
    column_count: int
    row_count: int | None = None
    primary_key: list[str] = Field(default_factory=list)
    description_auto: str | None = None
    description_manual: str | None = None
    business_meaning_auto: str | None = None
    business_meaning_manual: str | None = None
    domain_auto: str | None = None
    domain_manual: str | None = None
    semantic_label_manual: str | None = None
    semantic_table_role_manual: str | None = None
    semantic_grain_manual: str | None = None
    semantic_main_date_column_manual: str | None = None
    semantic_main_entity_manual: str | None = None
    semantic_synonyms: list[str] = Field(default_factory=list)
    semantic_important_metrics: list[str] = Field(default_factory=list)
    semantic_important_dimensions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    sensitivity: str | None = None
    usage_score: float | None = None
    columns: list[KnowledgeColumnRead] = Field(default_factory=list)
    relationships: list[KnowledgeRelationshipRead] = Field(default_factory=list)


class KnowledgeTableUpdate(BaseModel):
    description_manual: str | None = None
    business_meaning_manual: str | None = None
    domain_manual: str | None = None
    semantic_label_manual: str | None = None
    semantic_table_role_manual: str | None = None
    semantic_grain_manual: str | None = None
    semantic_main_date_column_manual: str | None = None
    semantic_main_entity_manual: str | None = None
    semantic_synonyms: list[str] | None = None
    semantic_important_metrics: list[str] | None = None
    semantic_important_dimensions: list[str] | None = None
    tags: list[str] | None = None
    sensitivity: str | None = None


class KnowledgeColumnUpdate(BaseModel):
    description_manual: str | None = None
    semantic_label_manual: str | None = None
    synonyms: list[str] | None = None
    sensitivity: str | None = None
    hidden_for_llm: bool | None = None


class KnowledgeRelationshipUpdate(BaseModel):
    cardinality: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    approved: bool | None = None
    is_disabled: bool | None = None
    description_manual: str | None = None


class KnowledgeSummaryResponse(BaseModel):
    database_id: str
    database_label: str
    dialect: str
    status: str
    database_description: str | None = None
    active_table_count: int = 0
    active_column_count: int = 0
    active_relationship_count: int = 0
    last_scan: KnowledgeScanRunRead | None = None
    scan_runs: list[KnowledgeScanRunRead] = Field(default_factory=list)
    dictionary_entries: list[DictionaryEntryRead] = Field(default_factory=list)
    tables: list[KnowledgeTableRead] = Field(default_factory=list)


class ERDNode(BaseModel):
    id: str
    label: str
    schema_name: str
    table_name: str
    column_count: int
    row_count: int | None = None
    tags: list[str] = Field(default_factory=list)


class ERDEdge(BaseModel):
    id: str
    source: str
    target: str
    source_label: str
    target_label: str
    relation_type: str
    confidence: float
    cardinality: str | None = None


class ERDGraphResponse(BaseModel):
    database_id: str
    nodes: list[ERDNode] = Field(default_factory=list)
    edges: list[ERDEdge] = Field(default_factory=list)
