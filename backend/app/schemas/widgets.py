from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


VisualizationType = Literal["table", "line", "bar", "area", "pie", "metric", "stacked_bar", "text"]
RefreshPolicy = Literal["manual", "on_view", "scheduled"]
SourceType = Literal["sql", "text_to_sql", "text"]


class WidgetRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    widget_id: str
    status: str
    columns: list[dict[str, Any]] | None = None
    rows_preview: list[dict[str, Any]] | None = None
    rows_preview_truncated: bool = False
    row_count: int = 0
    execution_time_ms: int = 0
    error_text: str | None = None
    started_at: datetime
    finished_at: datetime | None = None


class WidgetCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    source_type: SourceType = "sql"
    source_query_run_id: str | None = None
    dataset_id: str | None = None
    sql_text: str = ""
    visualization_type: VisualizationType = "table"
    visualization_config: dict[str, Any] | None = None
    chart_spec_json: dict[str, Any] | None = None
    refresh_policy: RefreshPolicy = "on_view"
    is_public: bool = False
    database_connection_id: str | None = None


class WidgetUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    sql_text: str | None = None
    dataset_id: str | None = None
    visualization_type: VisualizationType | None = None
    visualization_config: dict[str, Any] | None = None
    chart_spec_json: dict[str, Any] | None = None
    refresh_policy: RefreshPolicy | None = None
    is_public: bool | None = None


class WidgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None = None
    source_type: str
    source_query_run_id: str | None = None
    dataset_id: str | None = None
    sql_text: str
    visualization_type: str
    visualization_config: dict[str, Any] | None = None
    chart_spec_json: dict[str, Any] | None = None
    result_schema: dict[str, Any] | None = None
    refresh_policy: str
    is_public: bool
    owner_id: str
    database_connection_id: str | None = None
    created_at: datetime
    updated_at: datetime


class WidgetDetail(WidgetRead):
    last_run: WidgetRunRead | None = None
