from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.dashboards import DashboardDetail
from app.schemas.widgets import WidgetDetail

BiSemanticRole = Literal["dimension", "measure", "time", "unknown"]
BiDataType = Literal["string", "number", "date", "datetime", "boolean", "unknown"]
BiAggregation = Literal["sum", "avg", "count", "count_distinct", "min", "max", "none"]
BiChartType = Literal["table", "line", "bar", "area", "pie", "metric_card"]
BiFilterOperator = Literal["=", "!=", ">", ">=", "<", "<=", "in", "not_in", "between", "contains", "is_null", "is_not_null"]


class BiFieldRead(BaseModel):
    name: str
    source_type: str | None = None
    data_type: BiDataType = "unknown"
    semantic_role: BiSemanticRole = "unknown"
    default_aggregation: BiAggregation | None = None
    distinct_count: int | None = None
    sample_values: list[Any] = Field(default_factory=list)


class DatasetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    database_connection_id: str
    source_type: str
    source_query_execution_id: str
    sql: str
    columns_schema: list[dict[str, Any]] = Field(default_factory=list)
    fields: list[BiFieldRead] = Field(default_factory=list)
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    widgets_count: int = 0
    created_by: str
    created_at: datetime
    refresh_policy: str
    last_refresh_at: datetime | None = None


class DatasetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    refresh_policy: Literal["manual", "on_view", "scheduled"] | None = None


class DatasetPreviewResponse(BaseModel):
    dataset: DatasetRead
    columns: list[dict[str, Any]] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    rows_preview_truncated: bool = False


class BiFilterCondition(BaseModel):
    field: str
    operator: BiFilterOperator = "="
    value: Any = None


class BiChartEncoding(BaseModel):
    x_field: str | None = None
    y_field: str | None = None
    series_field: str | None = None
    facet_field: str | None = None
    aggregation: BiAggregation = "sum"
    sort: Literal["x_asc", "x_desc", "y_asc", "y_desc", "none"] | None = None
    normalize: Literal["none", "percent", "index_100", "running_total"] | None = None
    series_limit: int | None = Field(default=8, ge=1, le=50)
    category_limit: int | None = Field(default=50, ge=1, le=500)
    top_n_strategy: Literal["top_plus_other", "top_only", "none"] | None = "top_only"
    value_format: str | None = None


class BiChartSpec(BaseModel):
    chart_type: BiChartType
    title: str = Field(default="Визуализация", min_length=1, max_length=255)
    dataset_id: str | None = None
    encoding: BiChartEncoding = Field(default_factory=BiChartEncoding)
    filters: list[BiFilterCondition] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] | None = None
    variant: str | None = None
    explanation: str | None = None
    reason: str | None = None
    rule_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def normalize_stacked_bar(self) -> "BiChartSpec":
        # Keep frontend compatibility with the existing ChartCell renderer:
        # stacked bars are represented as chart_type=bar + variant=stacked.
        if self.chart_type == "area":
            self.options.setdefault("mark", "area")
        return self


class ChartValidationRequest(BaseModel):
    dataset_id: str
    chart_spec: BiChartSpec
    filters: list[BiFilterCondition] = Field(default_factory=list)


class ChartValidationResponse(BaseModel):
    valid: bool
    chart_spec: BiChartSpec | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sql: str | None = None


class ChartPreviewRequest(BaseModel):
    dataset_id: str
    chart_spec: BiChartSpec
    filters: list[BiFilterCondition] = Field(default_factory=list)


class ChartPreviewResponse(BaseModel):
    chart_spec: BiChartSpec
    sql: str
    columns: list[dict[str, Any]] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    rows_preview_truncated: bool = False
    execution_time_ms: int = 0
    warnings: list[str] = Field(default_factory=list)


class ChartRecommendationRead(BaseModel):
    title: str
    score: float = Field(ge=0, le=1)
    reason: str
    chart_spec: BiChartSpec


class ChartSaveRequest(BaseModel):
    dataset_id: str
    chart_spec: BiChartSpec
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    run_immediately: bool = True


class ChartSaveResponse(BaseModel):
    widget: WidgetDetail
    preview: ChartPreviewResponse | None = None


class QuickDashboardRequest(BaseModel):
    dataset_id: str | None = None
    title: str | None = Field(default=None, max_length=255)
    max_widgets: int = Field(default=4, ge=1, le=8)


class QuickDashboardResponse(BaseModel):
    dashboard: DashboardDetail
    widgets: list[WidgetDetail] = Field(default_factory=list)
    recommendations: list[ChartRecommendationRead] = Field(default_factory=list)
