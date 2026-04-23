from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ArtifactSource = Literal["schema_scan", "rule_engine", "stat_profile", "llm_enrichment", "validator"]
ArtifactStatus = Literal["validated", "suggested", "conflicted", "rejected"]
TableSemanticRole = Literal["fact", "dimension", "bridge", "lookup", "event", "snapshot", "unknown"]
ColumnSemanticRole = Literal[
    "id",
    "foreign_key",
    "timestamp",
    "date",
    "amount",
    "quantity",
    "status",
    "category",
    "name",
    "description",
    "code",
    "metric_proxy",
    "unknown",
]
MetricFamily = Literal["monetary", "countable_events", "quantity", "duration", "ratio", "balance", "inventory", "capacity"]
DimensionFamily = Literal["time", "geography", "product", "customer", "org", "category", "status", "channel", "type", "entity"]
JoinPathType = Literal["physical_fk", "inferred_fk", "fk_chain"]
ValidationSeverity = Literal["info", "warning", "error"]


class SemanticArtifact(BaseModel):
    value: str
    source: ArtifactSource
    confidence: float = 0.0
    provenance: list[str] = Field(default_factory=list)
    validation_status: ArtifactStatus = "validated"


class ColumnFact(BaseModel):
    schema_name: str
    table_name: str
    column_name: str
    db_type: str
    nullable: bool = True
    ordinal_position: int = 0
    is_primary_key: bool = False
    is_foreign_key: bool = False
    referenced_table: str | None = None
    referenced_column: str | None = None
    distinct_count: int | None = None
    null_ratio: float | None = None
    distinct_ratio: float | None = None
    top_values: list[str] = Field(default_factory=list)
    min_value: str | None = None
    max_value: str | None = None
    sample_values: list[str] = Field(default_factory=list)
    semantic_candidates: list[SemanticArtifact] = Field(default_factory=list)


class SchemaFact(BaseModel):
    database_id: str
    schema_name: str
    table_name: str
    row_count_estimate: int | None = None
    primary_key: list[str] = Field(default_factory=list)
    indexes: list[dict[str, Any]] = Field(default_factory=list)
    column_facts: list[ColumnFact] = Field(default_factory=list)
    foreign_keys: list[dict[str, Any]] = Field(default_factory=list)
    inferred_foreign_keys: list[dict[str, Any]] = Field(default_factory=list)


class GrainCandidate(BaseModel):
    grain: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class MetricCandidate(BaseModel):
    metric_name: str
    table: str
    column: str
    aggregation: str
    confidence: float = 0.0
    semantic_family: MetricFamily
    forbidden_proxies: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)


class DimensionCandidate(BaseModel):
    column: str
    semantic_role: str
    family: DimensionFamily | None = None
    confidence: float = 0.0
    provenance: list[str] = Field(default_factory=list)


class JoinPathCandidate(BaseModel):
    from_table: str
    to_table: str
    path: list[str] = Field(default_factory=list)
    path_type: JoinPathType = "fk_chain"
    confidence: float = 0.0
    provenance: list[str] = Field(default_factory=list)


class TableSemanticProfile(BaseModel):
    table: str
    table_role: TableSemanticRole = "unknown"
    confidence: float = 0.0
    grain_candidates: list[GrainCandidate] = Field(default_factory=list)
    main_date_column: str | None = None
    measure_candidates: list[MetricCandidate] = Field(default_factory=list)
    dimension_candidates: list[DimensionCandidate] = Field(default_factory=list)
    semantic_tags: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)


class SemanticValidationIssue(BaseModel):
    severity: ValidationSeverity = "warning"
    code: str
    message: str
    table: str | None = None
    column: str | None = None


class SemanticContract(BaseModel):
    database_id: str
    facts: list[SchemaFact] = Field(default_factory=list)
    table_profiles: list[TableSemanticProfile] = Field(default_factory=list)
    join_paths: list[JoinPathCandidate] = Field(default_factory=list)
    suggested_artifacts: list[SemanticArtifact] = Field(default_factory=list)
    validation_issues: list[SemanticValidationIssue] = Field(default_factory=list)

    @property
    def table_names(self) -> set[str]:
        return {fact.table_name for fact in self.facts}
