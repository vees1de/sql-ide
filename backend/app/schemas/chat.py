from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.query import ChartCandidate, ChartSpec, DateRange, DecisionSummary, FilterCondition, QueryInterpretation, QueryMode


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
    detail: str | None = None
    reason: str | None = None


AmbiguityType = Literal["metric", "dimension", "time_range", "aggregation", "other"]
ClarificationAnswerType = Literal["single_select", "multi_select", "free_text"]
ClarificationStatus = Literal["pending", "answered"]
MessageKind = Literal["answer", "clarification", "error"]
DebugTraceStatus = Literal["success", "warning", "error", "info"]
AgentState = Literal["CLARIFYING", "SQL_DRAFTING", "SQL_READY", "ERROR"]
ActionType = Literal["create_sql", "show_run_button", "show_chart_preview", "show_sql", "save_report"]
SemanticTermKind = Literal["metric", "dimension", "filter", "table", "column", "relationship", "term"]
SemanticTermSource = Literal["semantic_catalog", "schema", "dictionary", "user_input", "unknown"]


class ClarificationBlock(BaseModel):
    clarification_id: str
    question: str
    ambiguity_type: AmbiguityType = "other"
    answer_type: ClarificationAnswerType = "single_select"
    options: list[ClarificationOption] = Field(default_factory=list)
    recommended_option_id: str | None = None
    status: ClarificationStatus = "pending"
    answer_option_id: str | None = None
    answer_text: str | None = None


class ErrorBlock(BaseModel):
    message: str
    suggestions: list[str] = Field(default_factory=list)


class DebugTraceStep(BaseModel):
    stage: str
    status: DebugTraceStatus = "info"
    code: str | None = None
    detail: str


class ClarificationAnswerRequest(BaseModel):
    selected_option_id: str | None = None
    text_answer: str | None = None


class SemanticTermBinding(BaseModel):
    term: str
    kind: SemanticTermKind = "term"
    match: str | None = None
    source: SemanticTermSource = "unknown"
    confidence: float | None = None
    note: str | None = None


class SemanticParse(BaseModel):
    intent_summary: str | None = None
    metric: str | None = None
    dimensions: list[str] = Field(default_factory=list)
    date_range: DateRange | None = None
    filters: list[FilterCondition] = Field(default_factory=list)
    comparison: str | None = None
    resolved_terms: list[SemanticTermBinding] = Field(default_factory=list)
    unresolved_terms: list[SemanticTermBinding] = Field(default_factory=list)
    candidate_tables: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class CreateSqlActionPayload(BaseModel):
    reason: str | None = None


class ShowRunButtonActionPayload(BaseModel):
    sql_ready: bool = True
    require_user_confirmation: bool = True


class ShowChartPreviewActionPayload(BaseModel):
    reason: str | None = None


class ShowSqlActionPayload(BaseModel):
    expanded: bool = True


class SaveReportActionPayload(BaseModel):
    title_suggestion: str | None = None


class CreateSqlAction(BaseModel):
    type: Literal["create_sql"]
    label: str = "Подготовить SQL"
    primary: bool = False
    disabled: bool = False
    payload: CreateSqlActionPayload = Field(default_factory=CreateSqlActionPayload)


class ShowRunButtonAction(BaseModel):
    type: Literal["show_run_button"]
    label: str = "Запустить SQL"
    primary: bool = True
    disabled: bool = False
    payload: ShowRunButtonActionPayload = Field(default_factory=ShowRunButtonActionPayload)


class ShowChartPreviewAction(BaseModel):
    type: Literal["show_chart_preview"]
    label: str = "Показать график"
    primary: bool = False
    disabled: bool = False
    payload: ShowChartPreviewActionPayload = Field(default_factory=ShowChartPreviewActionPayload)


class ShowSqlAction(BaseModel):
    type: Literal["show_sql"]
    label: str = "Показать SQL"
    primary: bool = False
    disabled: bool = False
    payload: ShowSqlActionPayload = Field(default_factory=ShowSqlActionPayload)


class SaveReportAction(BaseModel):
    type: Literal["save_report"]
    label: str = "Сохранить отчёт"
    primary: bool = False
    disabled: bool = False
    payload: SaveReportActionPayload = Field(default_factory=SaveReportActionPayload)


AgentAction = Annotated[
    CreateSqlAction | ShowRunButtonAction | ShowChartPreviewAction | ShowSqlAction | SaveReportAction,
    Field(discriminator="type"),
]


class StructuredPayload(BaseModel):
    state: AgentState = "SQL_DRAFTING"
    assistant_message: str | None = None
    semantic_parse: SemanticParse | None = None
    actions: list[AgentAction] = Field(default_factory=list)
    interpretation: Interpretation
    tables_used: list[TableUsage] = Field(default_factory=list)
    sql: str | None = None
    warnings: list[str] = Field(default_factory=list)
    confidence_level: Literal["low", "medium", "high"] = "medium"
    confidence_reasons: list[str] = Field(default_factory=list)
    message_kind: MessageKind = "answer"
    clarification: ClarificationBlock | None = None
    error: ErrorBlock | None = None
    debug_trace: list[DebugTraceStep] = Field(default_factory=list)
    # Legacy fields kept for already-persisted messages. Frontend reads new fields first.
    needs_clarification: bool = False
    clarification_question: str | None = None
    clarification_options: list[ClarificationOption] | None = None
    answered_clarification_id: str | None = None
    dialect: str
    query_mode: QueryMode = "fast"
    llm_model_alias: str | None = None
    complexity: Literal["simple", "complex"] = "simple"
    mode_suggestion: QueryMode | None = None
    mode_suggestion_reason: str | None = None


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatSessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    archived: bool | None = None


class ChatMessageCreate(BaseModel):
    text: str = Field(min_length=1)
    query_mode: QueryMode = "fast"
    llm_model_alias: str | None = None


class SqlDraftUpdate(BaseModel):
    sql: str = Field(min_length=0)
    expected_version: int = Field(ge=0)


class ExecuteRequest(BaseModel):
    sql: str = Field(min_length=1)


class RunPreparedSqlRequest(BaseModel):
    sql: str | None = None


ChartSuggestionGoal = Literal["best_chart", "explain_visualization", "dashboard_ready"]


class ChartSuggestionRequest(BaseModel):
    goal: ChartSuggestionGoal = "best_chart"


class ExecutionDatasetRead(BaseModel):
    dataset_id: str
    query_execution_id: str
    row_count: int = 0
    columns: list[dict[str, Any]] = Field(default_factory=list)


class ChartRecommendation(BaseModel):
    recommended_view: Literal["table", "chart"]
    chart_type: str | None = None
    x: str | None = None
    y: str | None = None
    series: str | None = None
    facet: str | None = None
    variant: str | None = None
    explanation: str | None = None
    rule_id: str | None = None
    confidence: float | None = None
    data: dict[str, Any] | None = None
    reason: str
    semantic_intent: str | None = None
    analysis_mode: str | None = None
    visual_goal: str | None = None
    time_role: str | None = None
    comparison_goal: str | None = None
    preferred_mark: str | None = None
    normalize: str | None = None
    value_format: str | None = None
    series_limit: int | None = None
    category_limit: int | None = None
    top_n_strategy: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    candidates: list[ChartCandidate] = Field(default_factory=list)
    constraints_applied: list[str] = Field(default_factory=list)
    visual_load: int | None = None
    query_interpretation: QueryInterpretation | None = None
    decision_summary: DecisionSummary | None = None
    reason_codes: list[str] = Field(default_factory=list)
    chart_spec: ChartSpec | None = None
    ai_chart_spec: ChartSpec | None = None


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
    dataset: ExecutionDatasetRead | None = None
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
