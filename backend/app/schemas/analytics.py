from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.metadata import SchemaMetadataResponse
from app.schemas.semantic_catalog import SemanticCatalog
from app.schemas.query import ChartSpec, FilterCondition, IntentPayload


class AnalyticsContext(BaseModel):
    previous_intent: IntentPayload | dict[str, Any] | None = None
    previous_sql: str | None = None
    active_filters: list[FilterCondition] = Field(default_factory=list)
    active_dimensions: list[str] = Field(default_factory=list)
    database: str | None = None
    notebook_id: str | None = None


class AnalyticsQueryRequest(BaseModel):
    query: str = Field(min_length=1)
    context: AnalyticsContext = Field(default_factory=AnalyticsContext)


class ClarificationQuestion(BaseModel):
    id: str
    text: str
    options: list[str] = Field(default_factory=list)


class ClarificationResponse(BaseModel):
    questions: list[ClarificationQuestion] = Field(default_factory=list)


class ClarificationAnswer(BaseModel):
    id: str
    selected_option_id: str | None = None
    text_answer: str | None = None


class ClarificationRequest(BaseModel):
    query: str = Field(min_length=1)
    context: AnalyticsContext = Field(default_factory=AnalyticsContext)
    clarification_id: str | None = None
    answers: list[ClarificationAnswer] = Field(default_factory=list)


class DashboardMetadata(BaseModel):
    id: str
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    analysis_types: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    recency: float = 0.0
    popularity: float = 0.0


class ScoredDashboard(DashboardMetadata):
    score: float


class DashboardRecommendationResponse(BaseModel):
    best_match: ScoredDashboard | None = None
    alternatives: list[ScoredDashboard] = Field(default_factory=list)


class DashboardRecommendationRequest(BaseModel):
    intent: IntentPayload
    user_context: AnalyticsContext = Field(default_factory=AnalyticsContext)
    dashboards: list[DashboardMetadata] = Field(default_factory=list)


class AnalyticsResponse(BaseModel):
    intent: IntentPayload
    sql: str | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)
    chart: ChartSpec | None = None
    insight: str | None = None
    confidence: float = 0.0
    clarification: ClarificationResponse | None = None
    dashboard_recommendation: DashboardRecommendationResponse | None = None
    status: Literal["success", "clarification_required", "error"] = "success"
    error: str | None = None


class MetadataBundleResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_: SchemaMetadataResponse = Field(alias="schema")
    dictionary: list[dict[str, Any]] = Field(default_factory=list)
    catalog: SemanticCatalog | None = None
    notes: list[str] = Field(default_factory=list)


class NotebookSaveRequest(BaseModel):
    notebook_id: str | None = None
    workspace_id: str | None = None
    title: str | None = None
    database_id: str | None = None
    status: str | None = None
    context: AnalyticsContext = Field(default_factory=AnalyticsContext)
