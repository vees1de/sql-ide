from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


QueryMode = Literal["fast", "thinking"]


def normalize_query_mode(value: str | None) -> QueryMode:
    if isinstance(value, str) and value.strip().lower() == "thinking":
        return "thinking"
    return "fast"


class FilterCondition(BaseModel):
    field: str
    operator: str = "="
    value: Any


class DateRange(BaseModel):
    kind: str
    start: date | None = None
    end: date | None = None
    lookback_value: int | None = None
    lookback_unit: str | None = None


class IntentPayload(BaseModel):
    raw_prompt: str
    metric: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    filters: list[FilterCondition] = Field(default_factory=list)
    comparison: str | None = None
    date_range: DateRange | None = None
    visualization_preference: str | None = None
    ambiguities: list[str] = Field(default_factory=list)
    clarification_question: str | None = None
    confidence: float = 0.0
    follow_up: bool = False


class DimensionMapping(BaseModel):
    key: str
    label: str
    expression: str
    alias: str
    requires_join: str | None = None


class FilterMapping(BaseModel):
    field: str
    expression: str
    operator: str
    value: Any
    requires_join: str | None = None


class SemanticMappingPayload(BaseModel):
    metric_key: str | None = None
    metric_expression: str | None = None
    metric_alias: str | None = None
    time_expression: str | None = None
    base_alias: str = "t0"
    dimension_mappings: list[DimensionMapping] = Field(default_factory=list)
    filter_mappings: list[FilterMapping] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    base_table: str = "orders"
    joins: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    dialect: str


class ValidationPayload(BaseModel):
    valid: bool
    sql: str
    tables: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ChartEncoding(BaseModel):
    x_field: str | None = None
    y_field: str | None = None
    series_field: str | None = None


class ChartSpec(BaseModel):
    chart_type: str
    title: str
    encoding: ChartEncoding
    options: dict[str, Any] = Field(default_factory=dict)


class QueryExecutionResult(BaseModel):
    sql: str
    rows: list[dict[str, Any]] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: int = 0


class PromptRunRequest(BaseModel):
    prompt: str = Field(min_length=1)
    query_mode: QueryMode = "fast"
    llm_model_alias: str | None = None


class PromptRunResponse(BaseModel):
    notebook_id: str
    query_run_id: str
    prompt_cell_id: str
    generated_cell_ids: list[str] = Field(default_factory=list)
    status: str


class CellContent(BaseModel):
    model_config = ConfigDict(extra="allow")


class CellRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    notebook_id: str
    query_run_id: str | None = None
    type: str
    position: int
    content: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class QueryRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    notebook_id: str
    prompt_cell_id: str
    prompt_text: str
    sql: str
    explanation: dict[str, Any]
    agent_trace: dict[str, Any]
    confidence: float
    execution_time_ms: int
    row_count: int
    status: str
    error_message: str | None = None
    created_at: datetime


@dataclass
class ClarificationAnswerRecord:
    clarification_id: str
    ambiguity_type: str
    option_id: str | None = None
    option_label: str | None = None
    text_answer: str | None = None


@dataclass
class QueryContext:
    previous_intent: IntentPayload | None = None
    notebook_title: str = ""
    original_prompt: str = ""
    clarification_answers: list[ClarificationAnswerRecord] = field(default_factory=list)
