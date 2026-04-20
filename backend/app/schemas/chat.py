from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.query import DateRange, FilterCondition


class Interpretation(BaseModel):
    metric: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    date_range: DateRange | None = None
    filters: list[FilterCondition] = Field(default_factory=list)
    comparison: str | None = None
    ambiguities: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class TableUsage(BaseModel):
    table: str
    reason: str


class ClarificationOption(BaseModel):
    id: str
    label: str
    detail: str


class StructuredPayload(BaseModel):
    interpretation: Interpretation
    tables_used: list[TableUsage] = Field(default_factory=list)
    sql: str | None = None
    warnings: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_question: str | None = None
    clarification_options: list[ClarificationOption] | None = None
    dialect: str


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatSessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    archived: bool | None = None


class ChatMessageCreate(BaseModel):
    text: str = Field(min_length=1)


class SqlDraftUpdate(BaseModel):
    sql: str = Field(min_length=0)
    expected_version: int = Field(ge=0)


class ExecuteRequest(BaseModel):
    sql: str = Field(min_length=1)


class ChartRecommendation(BaseModel):
    recommended_view: Literal["table", "chart"]
    chart_type: str | None = None
    x: str | None = None
    y: str | None = None
    series: str | None = None
    reason: str


class ChatMessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    role: str
    text: str
    structured_payload: StructuredPayload | None = None
    created_at: datetime


class ChatSessionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    database_connection_id: str
    title: str
    current_sql_draft: str | None = None
    sql_draft_version: int = 0
    last_executed_sql: str | None = None
    last_intent_json: dict[str, Any] | None = None
    archived: bool = False
    created_at: datetime
    updated_at: datetime


class ChatSessionDetail(ChatSessionRead):
    messages: list[ChatMessageRead] = Field(default_factory=list)
    last_execution: QueryExecutionRead | None = None


class QueryExecutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    session_id: str
    sql_text: str
    columns: list[dict[str, Any]] | None = None
    rows_preview: list[dict[str, Any]] | None = None
    rows_preview_truncated: bool = False
    row_count: int = 0
    execution_time_ms: int = 0
    chart_recommendation: ChartRecommendation | None = None
    error_message: str | None = None
    created_at: datetime


class SendMessageResponse(BaseModel):
    session: ChatSessionRead
    user_message: ChatMessageRead
    assistant_message: ChatMessageRead
    sql_draft: str | None = None
    sql_draft_version: int


class ExecuteResponse(BaseModel):
    session: ChatSessionRead
    execution: QueryExecutionRead


ChatSessionDetail.model_rebuild()
