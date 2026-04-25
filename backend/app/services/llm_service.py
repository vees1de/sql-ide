from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import TYPE_CHECKING
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

from app.core.config import settings
from app.schemas.chat import AgentAction, AgentState, SemanticParse, SqlExplanationBlock, SqlExplanationResponse
from app.schemas.metadata import SchemaMetadataResponse
from app.schemas.query import IntentPayload, QuerySemantics
from app.schemas.semantic_catalog import SemanticCatalog, SemanticTable, SemanticTableEnrichment
from app.schemas.semantic_contract import SemanticContract

if TYPE_CHECKING:
    from app.services.llm_schema_recon_service import LLMSchemaReconToolbox

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - runtime optional dependency
    OpenAI = None


logger = logging.getLogger(__name__)


_ALLOWED_AGENT_STATES = {"CLARIFYING", "SQL_DRAFTING", "SQL_READY", "ERROR"}
_ALLOWED_SEMANTIC_SOURCES = {"semantic_catalog", "schema", "dictionary", "user_input", "unknown"}
_ALLOWED_VISUALIZATION_HINTS = {"line", "bar", "pie", "table", "metric_card"}
_ALLOWED_ANALYSIS_MODES = {"compare", "trend", "compose", "rank", "correlate", "distribute", "delta"}
_ALLOWED_TIME_ROLES = {"primary", "secondary", "none"}
_ALLOWED_COMPARISON_GOALS = {"absolute", "composition", "delta", "rank"}
_ALLOWED_PREFERRED_MARKS = {"line", "bar", "area", "point", "arc", "stat"}
_ALLOWED_TIME_GRAIN = {"day", "week", "month", "quarter", "year"}
_ALLOWED_COMPARISON_KINDS = {"period_over_period", "entity_vs_entity", "none"}
_SEMANTIC_TERM_KIND_ALIASES = {
    "metric": "metric",
    "metric_definition": "metric",
    "metric_column": "metric",
    "measure": "metric",
    "measure_column": "metric",
    "kpi": "metric",
    "dimension": "dimension",
    "time_dimension": "dimension",
    "category": "dimension",
    "grouping": "dimension",
    "filter": "filter",
    "status_value": "filter",
    "enum": "filter",
    "enum_value": "filter",
    "predicate": "filter",
    "table": "table",
    "column": "column",
    "field": "column",
    "timestamp": "column",
    "time_event": "column",
    "relationship": "relationship",
    "join_path": "relationship",
    "join": "relationship",
    "fk": "relationship",
    "entity_fk": "relationship",
    "term": "term",
}


def _normalize_agent_state(value: Any, *, payload: dict[str, Any]) -> str | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    if candidate in _ALLOWED_AGENT_STATES:
        return candidate

    normalized = candidate.upper().replace("-", "_").replace(" ", "_")
    if normalized in _ALLOWED_AGENT_STATES:
        return normalized

    has_sql = bool(payload.get("sql"))
    intent = payload.get("intent") or {}
    has_clarification = bool(intent.get("clarification_question"))

    if "CLARIFYING" in normalized and has_clarification and not has_sql:
        return "CLARIFYING"
    if "SQL_READY" in normalized and has_sql:
        return "SQL_READY"
    if "SQL_DRAFTING" in normalized:
        return "SQL_DRAFTING"
    if "ERROR" in normalized:
        return "ERROR"
    return None


def _normalize_date_range_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value

    payload = dict(value)
    kind = str(payload.get("kind") or "").strip().lower()
    if kind in {"absolute", "relative", "all", "ytd"}:
        payload["kind"] = kind
    elif payload.get("lookback_value") is not None or payload.get("lookback_unit"):
        payload["kind"] = "relative"
    elif payload.get("start") or payload.get("end"):
        payload["kind"] = "absolute"
    else:
        payload["kind"] = "absolute"
    return payload


def _normalize_semantic_term_kind(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if not candidate:
        return "term"
    if candidate in _SEMANTIC_TERM_KIND_ALIASES:
        return _SEMANTIC_TERM_KIND_ALIASES[candidate]
    if "metric" in candidate or "measure" in candidate or "kpi" in candidate:
        return "metric"
    if "dimension" in candidate or "group" in candidate or "time" in candidate:
        return "dimension"
    if "filter" in candidate or "status" in candidate or "enum" in candidate or "predicate" in candidate:
        return "filter"
    if "table" in candidate:
        return "table"
    if "column" in candidate or "field" in candidate or "timestamp" in candidate:
        return "column"
    if "relationship" in candidate or "join" in candidate or "fk" in candidate:
        return "relationship"
    return "term"


def _normalize_semantic_source(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in _ALLOWED_SEMANTIC_SOURCES else "unknown"


def _normalize_semantic_term_bindings(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    bindings: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        binding = dict(item)
        binding["kind"] = _normalize_semantic_term_kind(binding.get("kind"))
        binding["source"] = _normalize_semantic_source(binding.get("source"))
        bindings.append(binding)
    return bindings


def _normalize_visualization_hint(value: Any) -> str | None:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in _ALLOWED_VISUALIZATION_HINTS else None


def _normalize_intent_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value

    payload = dict(value)
    payload["date_range"] = _normalize_date_range_payload(payload.get("date_range"))
    payload["clarification_options"] = list(payload.get("clarification_options") or [])
    payload["visualization_preference"] = _normalize_visualization_hint(payload.get("visualization_preference"))
    return payload


def _normalize_semantics_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value

    payload = dict(value)
    analysis_mode = str(payload.get("analysis_mode") or "").strip().lower()
    payload["analysis_mode"] = analysis_mode if analysis_mode in _ALLOWED_ANALYSIS_MODES else None

    time_role = str(payload.get("time_role") or "").strip().lower()
    payload["time_role"] = time_role if time_role in _ALLOWED_TIME_ROLES else None

    comparison_goal = str(payload.get("comparison_goal") or "").strip().lower()
    payload["comparison_goal"] = comparison_goal if comparison_goal in _ALLOWED_COMPARISON_GOALS else None

    preferred_mark = str(payload.get("preferred_mark") or "").strip().lower()
    payload["preferred_mark"] = preferred_mark if preferred_mark in _ALLOWED_PREFERRED_MARKS else None

    payload["visualization_hint"] = _normalize_visualization_hint(payload.get("visualization_hint"))

    time_payload = payload.get("time")
    if isinstance(time_payload, dict):
        normalized_time = dict(time_payload)
        granularity = str(normalized_time.get("granularity") or "").strip().lower()
        normalized_time["granularity"] = granularity if granularity in _ALLOWED_TIME_GRAIN else None
        normalized_time["range"] = _normalize_date_range_payload(normalized_time.get("range"))
        payload["time"] = normalized_time

    comparison_payload = payload.get("comparison")
    if isinstance(comparison_payload, dict):
        normalized_comparison = dict(comparison_payload)
        comparison_kind = str(normalized_comparison.get("kind") or "").strip().lower()
        normalized_comparison["kind"] = comparison_kind if comparison_kind in _ALLOWED_COMPARISON_KINDS else "none"
        normalized_comparison["baseline_period"] = _normalize_date_range_payload(
            normalized_comparison.get("baseline_period")
        )
        payload["comparison"] = normalized_comparison

    return payload


def _normalize_semantic_parse_payload(value: Any) -> Any:
    if not isinstance(value, dict):
        return value

    payload = dict(value)
    payload["date_range"] = _normalize_date_range_payload(payload.get("date_range"))
    payload["resolved_terms"] = _normalize_semantic_term_bindings(payload.get("resolved_terms"))
    payload["unresolved_terms"] = _normalize_semantic_term_bindings(payload.get("unresolved_terms"))
    return payload


class LLMQueryPlan(BaseModel):
    state: AgentState | None = None
    assistant_message: str | None = None
    semantic_parse: SemanticParse | None = None
    actions: list[AgentAction] = Field(default_factory=list)
    intent: IntentPayload
    semantics: QuerySemantics | None = None
    sql: str | None = None
    chart_type: str | None = None
    chart_x_field: str | None = None
    chart_y_field: str | None = None
    visualization_hint: str | None = None
    chart_title: str | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_contract(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        payload = dict(value)
        payload["state"] = _normalize_agent_state(payload.get("state"), payload=payload)
        payload["intent"] = _normalize_intent_payload(payload.get("intent") or {})
        payload["semantic_parse"] = _normalize_semantic_parse_payload(payload.get("semantic_parse") or {})
        payload["semantics"] = _normalize_semantics_payload(payload.get("semantics") or {})
        payload["chart_type"] = _normalize_visualization_hint(payload.get("chart_type"))
        payload["visualization_hint"] = _normalize_visualization_hint(payload.get("visualization_hint"))

        intent = payload.get("intent") or {}
        semantic_parse = payload.get("semantic_parse") or {}

        if not payload.get("assistant_message"):
            if payload.get("sql"):
                payload["assistant_message"] = "SQL draft is ready."
            elif intent.get("clarification_question"):
                payload["assistant_message"] = intent.get("clarification_question")

        if not payload.get("state"):
            if intent.get("clarification_question") and not payload.get("sql"):
                payload["state"] = "CLARIFYING"
            elif payload.get("sql"):
                payload["state"] = "SQL_READY"
            elif payload.get("assistant_message") and not payload.get("sql"):
                payload["state"] = "SQL_DRAFTING"
            else:
                payload["state"] = "ERROR"

        if not payload.get("intent") and semantic_parse:
            semantic_notes = semantic_parse.get("notes") or []
            payload["intent"] = {
                "raw_prompt": "",
                "metric": semantic_parse.get("metric"),
                "dimensions": semantic_parse.get("dimensions") or [],
                "filters": semantic_parse.get("filters") or [],
                "comparison": semantic_parse.get("comparison"),
                "date_range": semantic_parse.get("date_range"),
                "ambiguities": [item.get("term") for item in semantic_parse.get("unresolved_terms") or [] if item.get("term")],
                "clarification_question": semantic_notes[0] if semantic_parse.get("unresolved_terms") and semantic_notes else None,
                "confidence": semantic_parse.get("confidence", 0.0),
                "follow_up": False,
            }
        return payload


class LLMSqlRepairPayload(BaseModel):
    sql: str | None = None
    reason: str | None = None
    retryable: bool = True
    warnings: list[str] = Field(default_factory=list)


class LLMChartSuggestionPayload(BaseModel):
    chart_type: str | None = None
    variant: str | None = None
    title: str | None = None
    x_field: str | None = None
    y_field: str | None = None
    series_field: str | None = None
    facet_field: str | None = None
    normalize: str | None = None
    sort: str | None = None
    reason: str | None = None
    explanation: str | None = None
    confidence: float | None = None


class LLMSqlExplanationBlock(BaseModel):
    index: int
    kind: str = "other"
    title: str
    line_start: int
    line_end: int
    sql: str
    explanation: str


class LLMSqlExplanationPayload(BaseModel):
    summary: str
    blocks: list[LLMSqlExplanationBlock] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class LLMService:
    def __init__(self) -> None:
        self._client: OpenAI | None = None

    @property
    def configured(self) -> bool:
        return self._configured_for_model(settings.llm_model)

    def _configured_for_model(self, model: str | None) -> bool:
        return bool(
            OpenAI is not None
            and settings.llm_api_base_url
            and settings.llm_api_key
            and model
        )

    def plan_query(
        self,
        prompt: str,
        schema: SchemaMetadataResponse,
        semantic_catalog: SemanticCatalog | None = None,
        semantic_contract: SemanticContract | None = None,
        semantic_notes: list[str] | None = None,
        previous_intent: IntentPayload | None = None,
        history_text: str | None = None,
        temperature: float = 0.1,
        model: str | None = None,
        schema_toolbox: "LLMSchemaReconToolbox | None" = None,
        few_shot_examples: list[dict] | None = None,
    ) -> LLMQueryPlan | None:
        target_model = model or settings.llm_model
        if not self._configured_for_model(target_model):
            return None

        previous_intent_payload = previous_intent.model_dump(mode="json") if previous_intent else None
        schema_summary = self._format_schema(schema)
        system_prompt = (
            "You are a senior analytics engineer. "
            "Return exactly one JSON object and no markdown. "
            "Your job is to understand the analytics request, decide whether clarification is needed, "
            "and draft a single safe read-only SELECT query when possible. You may also answer a schema or "
            "column meaning question directly in natural language when the user is not asking for a computation.\n"
            "Rules:\n"
            "1. Use only tables, columns, and relationships from the schema.\n"
            "2. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, COPY, GRANT or transaction statements.\n"
            "3. Prefer explicit JOINs and explicit aliases.\n"
            "4. Keep SQL compatible with the provided SQL dialect.\n"
            "5. Never execute SQL or imply that it was executed. The user must explicitly press Run.\n"
            "6. First clarify or explore schema semantics when needed, then draft SQL.\n"
            "6b. If the user asks what a column, table, or status means, answer in plain language from the "
            "available schema or semantic catalog. In that case, set state to SQL_DRAFTING, leave sql null, "
            "and include a create_sql action labeled like \"Выгрузить таблицу\" only when a table export "
            "would help the user follow up.\n"
            "7. Treat the semantic layer and semantic catalog as the source of truth for business terms, metrics, dimensions, and allowed join paths.\n"
            "8. If a business term is not grounded in the semantic layer, ask for clarification instead of guessing.\n"
            "9. Clarifications are welcome when they genuinely help pin down user intent — e.g. "
            "choosing between plausible metric definitions (what counts as 'completed'?), join paths, "
            "status value semantics, or a missing time window. A well-grounded clarification beats a "
            "wrong SQL. That said, do NOT ask when the user already specified the relevant detail: "
            "grouping (e.g. 'по часам', 'by hour', 'по водителям', 'по driver_id'), the metric "
            "(e.g. 'конверсия', 'completion rate', 'доля ...'), the filter "
            "(e.g. 'за 14 апреля 2026', 'только завершённые заказы'), or the chart type — in those "
            "cases proceed directly with SQL. If the user listed multiple metrics in one request "
            "(e.g. 'количество созданных, количество завершённых и конверсию'), return a single SQL "
            "that produces all of them as separate columns; do NOT ask which metric to pick. Set "
            "clarification_question to null and populate sql whenever the request is specific enough "
            "to write a safe SELECT.\n"
            "9b. NEVER silently invent a full-history date filter from the observed min/max range. "
            "If the request is a broad analytical summary, comparison, trend, funnel, conversion, "
            "operational performance analysis, or asks 'where / when / how often' without an explicit "
            "period, ask for the period and keep sql=null. Only use the full observed history when the "
            "user explicitly asks for 'all time', 'весь период', 'за всё время', or equivalent.\n"
            "10. Keep warnings concise.\n"
            "11. Match the user's language in clarification text.\n"
            "12. Use conversation history when provided to resolve follow-up intent.\n"
            "13. Prefer join paths that are present in relationship_graph when choosing table traversal.\n"
            "14. When you set clarification_question, ALSO populate clarification_options with 3–5 concrete, "
            "actionable answer choices specific to the user's request and the actual schema. "
            "Each option must have a stable machine id (snake_case), a short human-readable label, and "
            "optionally a detail/reason explaining the choice. Do NOT use generic placeholder options — "
            "derive them from the real tables, columns, values, date ranges, or structural choices at play. "
            "Examples of good options: {id:'limit_10', label:'Топ 10'}; "
            "{id:'join_via_match_table', label:'Через таблицу match', detail:'match.league_id → league.id связывает команды с лигой'}; "
            "{id:'year_2013_2015', label:'2013–2015', detail:'Три сезона'}. "
            "Write labels and details in the user's language.\n"
            "11. SCHEMA GROUNDING — both in SQL and in clarification_options, reference ONLY tables and "
            "columns that appear in the provided schema. Never invent a table name (e.g. do not propose "
            "a 'player_league' bridge table if it is not listed). If no relationship exists to express "
            "what the user asked, offer honest alternatives ('нет прямой связи — показать всё без фильтра', "
            "'использовать косвенную связь через таблицу X') instead of fabricating structure.\n"
            "12. SNAPSHOT / TIME-SERIES AWARENESS — if a table contains a date/timestamp column together "
            "with a foreign-key id (e.g. `player_attributes(player_api_id, date, overall_rating)`), it is "
            "almost always a time-series with multiple rows per entity. When joining such a table to its "
            "parent, you MUST either: (a) pick the latest snapshot per entity via `DISTINCT ON` or a "
            "`WHERE date = (SELECT MAX(date) ... WHERE player_api_id = ...)`, or (b) aggregate with "
            "`GROUP BY entity` and `MAX/AVG`. Never do a plain JOIN without one of these — it silently "
            "multiplies rows and ranks the same entity many times.\n"
            "13. DATE REALISM — when schema columns carry `observed_range: {min,max}`, any date filter "
            "you propose in SQL or clarification_options MUST fall within that observed range. Do NOT "
            "use `today()` or `CURRENT_DATE - INTERVAL '2 years'` if the data ends in 2016. Prefer "
            "absolute ranges like '2013–2015' grounded in the observed min/max.\n"
            "14. LIMIT DEFAULTS — if the user's request uses words like 'покажи', 'найди', 'топ', 'show', "
            "'list', 'find', 'best', 'worst' and no explicit count is given, either add `LIMIT 50` to the "
            "SQL by default OR include a limit option (`limit_10`, `limit_50`, `limit_all`) in "
            "clarification_options. Do NOT return thousands of rows by accident.\n"
            "15. NULL HANDLING — when `ORDER BY ... DESC` on a nullable metric column, add `NULLS LAST` "
            "AND a `WHERE <col> IS NOT NULL` filter, otherwise NULL rows float to the top and the output "
            "looks broken. Same for division: always guard denominator with `NULLIF(denom, 0)` AND filter "
            "`WHERE denom IS NOT NULL AND numerator IS NOT NULL`.\n"
            "16. AVOID BOGUS CROSS JOIN — never `CROSS JOIN` a dimension table to a scalar subquery that "
            "is not correlated to it. If you find yourself writing `FROM league CROSS JOIN (SELECT "
            "COUNT(*) FROM player_attributes ...)`, you are computing the same number for every row. "
            "Use a correlated subquery or a proper join path through a real relationship.\n"
            "17. SEMANTIC OUTPUT — return structured visualization semantics. Do NOT choose chart_type as "
            "the final answer; chart_type is decided by the backend rule engine. If you can infer a useful "
            "visualization hint, set visualization_hint, but treat it as a hint only.\n"
            "18. ANALYTICAL CONTRACT — separate semantic intent from visual strategy. Populate semantics.intent "
            "with the analytical task, preferring: trend, comparison, comparison_over_time, share, "
            "composition_over_time, distribution, correlation, ranking, kpi, delta. Populate "
            "semantics.analysis_mode with one of compare, trend, compose, rank, correlate, distribute, delta. "
            "Populate semantics.visual_goal with a short machine-readable goal such as compare_between_groups, "
            "compare_between_groups_over_time, compare_ranked_categories, show_composition, "
            "compare_structure_over_time, show_change_over_time.\n"
            "19. SEMANTIC FLAGS — set semantics.flags.is_time_series when the request is about a temporal "
            "trend or the chosen time column should drive the x-axis. Set is_comparison when the request "
            "compares entities or periods. Set is_ranking=true when the request asks for top-N / bottom-N / "
            "«топ» / «худшие» / ordering of entities by a metric (even if the result also has a rate column). "
            "Set is_share=true when the metric is a ratio, share or conversion rate. Set top_n to the "
            "requested number when the user asks for a specific N. Set explicit_chart_request only when the "
            "user explicitly names a chart type.\n"
            "20. ROLE ANNOTATION — populate semantics.time_role as primary, secondary, or none. Populate "
            "semantics.comparison_goal as absolute, composition, delta, or rank. Populate semantics.preferred_mark "
            "as line, bar, area, point, arc, or stat only when it is strongly implied by the analytical task.\n"
            "21. DATA ROLES — populate semantics.data_roles with x, y, series_key, facet_key, label, value "
            "using SQL aliases where possible. Also populate semantics.columns with semantic roles such as "
            "dimension_time, dimension_series, dimension_category, metric_primary. Populate semantics.metric.name "
            "with the SQL alias of the primary metric column (e.g. 'share_not_completed', 'completion_rate'), "
            "so the chart engine can pick the correct Y axis.\n"
            "22. ASSUMPTIONS AND AMBIGUITIES — populate semantics.assumptions with explicit defaults you had to "
            "adopt (aggregation, default time range, top-N fallback, etc.). Populate semantics.ambiguities with "
            "remaining uncertainty instead of hiding it. Keep both concise.\n"
            "23. COMPARISON SEMANTICS — when comparing periods or entities, fill semantics.comparison.kind "
            "with 'period_over_period' or 'entity_vs_entity', populate semantics.comparison.entities when "
            "concrete entities are mentioned, and set semantics.comparison.facet_column when the user explicitly "
            "asks for separate small multiples per category.\n"
            "24. SCHEMA TRUTH GUARD — if a table exists in schema truth but was not retrieved into the short context, "
            "you must treat it as existing-but-not-retrieved, not missing. Never ask 'table X is absent' unless "
            "schema truth also says it is absent.\n"
            "25. FACTS BEFORE GUESSES — prefer semantic_contract facts and rule-derived profiles over text hints. "
            "Use llm-style semantic guesses only as low-confidence tie-breakers.\n"
            f"{self._drivee_domain_guidance(schema)}"
            f"{self._schema_tool_guidance(enabled=bool(schema_toolbox))}"
            f"{self._alias_contract_guidance()}"
            f"{self._semantic_catalog_guidance(enabled=semantic_catalog is not None)}"
            f"{self._few_shot_guidance(enabled=bool(few_shot_examples))}"
            "{"
            '"state":"CLARIFYING|SQL_DRAFTING|SQL_READY|ERROR",'
            '"assistant_message":"string",'
            '"semantic_parse":{"intent_summary":"string|null","metric":"string|null","dimensions":["string"],'
            '"filters":[{"field":"string","operator":"string","value":"any"}],"comparison":"string|null",'
            '"date_range":{"kind":"absolute|relative","start":"YYYY-MM-DD|null","end":"YYYY-MM-DD|null","lookback_value":"number|null","lookback_unit":"string|null"}|null,'
            '"resolved_terms":[{"term":"string","kind":"string","match":"string|null","source":"semantic_catalog|schema|dictionary|user_input|unknown","confidence":"number|null","note":"string|null"}],'
            '"unresolved_terms":[{"term":"string","kind":"string","match":"string|null","source":"semantic_catalog|schema|dictionary|user_input|unknown","confidence":"number|null","note":"string|null"}],'
            '"candidate_tables":["string"],"notes":["string"],"confidence":"number"},'
            '"actions":[{"type":"create_sql|show_run_button|show_chart_preview|show_sql|save_report","label":"string","primary":"boolean","disabled":"boolean","payload":"object"}],'
            '"intent":{"raw_prompt":"string","metric":"string|null","dimensions":["string"],'
            '"filters":[{"field":"string","operator":"string","value":"any"}],'
            '"comparison":"string|null","date_range":{"kind":"absolute|relative","start":"YYYY-MM-DD|null",'
            '"end":"YYYY-MM-DD|null","lookback_value":"number|null","lookback_unit":"string|null"}|null,'
            '"visualization_preference":"line|bar|pie|table|null","ambiguities":["string"],'
            '"clarification_question":"string|null",'
            '"clarification_options":[{"id":"string","label":"string","detail":"string|null","reason":"string|null"}],'
            '"confidence":"number","follow_up":"boolean"},'
            '"semantics":{"intent":"string|null","visual_goal":"string|null","analysis_mode":"compare|trend|compose|rank|correlate|distribute|delta|null","time_role":"primary|secondary|none|null","comparison_goal":"absolute|composition|delta|rank|null","preferred_mark":"line|bar|area|point|arc|stat|null","metric":{"name":"string|null","aggregation":"string|null","unit":"string|null"}|null,'
            '"dimensions":[{"name":"string","role":"category"}],"columns":[{"name":"string","role":"string"}],"data_roles":{"x":"string|null","y":"string|null","series_key":"string|null","facet_key":"string|null","label":"string|null","value":"string|null"}|null,"time":{"column":"string|null","granularity":"day|week|month|quarter|year|null","range":{"kind":"absolute|relative","start":"YYYY-MM-DD|null","end":"YYYY-MM-DD|null","lookback_value":"number|null","lookback_unit":"string|null"}|null}|null,'
            '"comparison":{"kind":"period_over_period|entity_vs_entity|none","entities":["string"],"baseline_period":{"kind":"absolute|relative","start":"YYYY-MM-DD|null","end":"YYYY-MM-DD|null","lookback_value":"number|null","lookback_unit":"string|null"}|null,"series_column":"string|null","facet_column":"string|null"}|null,'
            '"filters":[{"field":"string","operator":"string","value":"any"}],'
            '"assumptions":["string"],"ambiguities":["string"],'
            '"flags":{"is_time_series":"boolean","is_comparison":"boolean","is_ranking":"boolean","is_share":"boolean","top_n":"number|null","explicit_chart_request":"boolean"},'
            '"visualization_hint":"line|bar|pie|table|metric_card|null","confidence_score":"number","clarification_needed":"string|null"},'
            '"sql":"string|null","chart_type":"line|bar|pie|table|metric_card|null","chart_x_field":"string|null",'
            '"chart_y_field":"string|null","visualization_hint":"line|bar|pie|table|metric_card|null","chart_title":"string|null","warnings":["string"]}'
        )
        user_prompt = json.dumps(
            {
                "today": date.today().isoformat(),
                "dialect": schema.dialect,
                "schema": schema_summary,
                "semantic_catalog": self._format_semantic_catalog(semantic_catalog),
                "semantic_contract": self._format_semantic_contract(semantic_contract),
                "semantic_notes": list(semantic_notes or []),
                "previous_intent": previous_intent_payload,
                "history_text": history_text,
                "alias_contract": self._alias_contract_reference(),
                "available_tools": self._tool_names(schema_toolbox),
                "few_shot_examples": few_shot_examples or [],
                "user_prompt": prompt,
            },
            ensure_ascii=False,
            indent=2,
        )

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            if schema_toolbox is not None:
                try:
                    content = self._chat_json_with_tools(
                        messages=messages,
                        tools=schema_toolbox.tool_specs(),
                        tool_executor=schema_toolbox.execute_tool,
                        max_rounds=4,
                        max_tokens=2200,
                        temperature=temperature,
                        model=target_model,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("LLM planning tool-call loop failed, falling back to plain planning: %s", exc)
                    content = self._chat_json(
                        messages=messages,
                        max_tokens=2200,
                        temperature=temperature,
                        model=target_model,
                    )
            else:
                content = self._chat_json(
                    messages=messages,
                    max_tokens=2200,
                    temperature=temperature,
                    model=target_model,
                )
            payload = json.loads(self._extract_json_object(content))
            payload.setdefault("intent", {})
            payload["intent"].setdefault("raw_prompt", prompt)
            payload.setdefault("semantics", {})
            return LLMQueryPlan.model_validate(payload)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Failed to parse LLM query plan: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM planning request failed: %s", exc)
        return None

    def _format_semantic_contract(self, contract: SemanticContract | None) -> dict[str, Any] | None:
        if contract is None:
            return None
        return {
            "table_names": sorted(contract.table_names),
            "table_profiles": [
                {
                    "table": profile.table,
                    "table_role": profile.table_role,
                    "confidence": profile.confidence,
                    "main_date_column": profile.main_date_column,
                    "measure_candidates": [
                        {
                            "metric_name": metric.metric_name,
                            "column": metric.column,
                            "family": metric.semantic_family,
                            "confidence": metric.confidence,
                            "forbidden_proxies": list(metric.forbidden_proxies),
                        }
                        for metric in profile.measure_candidates[:4]
                    ],
                    "dimension_candidates": [
                        {
                            "column": dimension.column,
                            "role": dimension.semantic_role,
                            "family": dimension.family,
                            "confidence": dimension.confidence,
                        }
                        for dimension in profile.dimension_candidates[:4]
                    ],
                    "semantic_tags": list(profile.semantic_tags),
                }
                for profile in contract.table_profiles
            ],
            "join_paths": [
                {
                    "from_table": path.from_table,
                    "to_table": path.to_table,
                    "path": list(path.path),
                    "confidence": path.confidence,
                }
                for path in contract.join_paths[:25]
            ],
            "validation_issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                    "table": issue.table,
                    "column": issue.column,
                }
                for issue in contract.validation_issues[:10]
            ],
        }

    def repair_sql(
        self,
        *,
        prompt: str,
        schema: SchemaMetadataResponse,
        failed_sql: str,
        failure_reason: str,
        semantic_catalog: SemanticCatalog | None = None,
        semantic_notes: list[str] | None = None,
        previous_intent: IntentPayload | None = None,
        history_text: str | None = None,
        row_count: int | None = None,
        execution_columns: list[str] | None = None,
        execution_rows: list[dict[str, Any]] | None = None,
        attempt_index: int = 0,
        model: str | None = None,
        schema_toolbox: "LLMSchemaReconToolbox | None" = None,
    ) -> LLMSqlRepairPayload | None:
        target_model = model or settings.llm_model
        if not self._configured_for_model(target_model):
            return None

        previous_intent_payload = previous_intent.model_dump(mode="json") if previous_intent else None
        system_prompt = (
            "You are repairing a failed text-to-SQL attempt. "
            "Return exactly one JSON object and no markdown. "
            "Preserve the original business intent. Only fix SQL mistakes, wrong enum values, wrong join paths, "
            "empty-result filters, or alias contract violations.\n"
            "Rules:\n"
            "1. Return a single safe read-only SELECT.\n"
            "2. Keep aliases stable and analytics-friendly.\n"
            "3. If the previous SQL used a likely-wrong enum value, date filter, or join path, correct it.\n"
            "4. If the previous SQL returned zero rows, prefer fixing the wrong predicate over broadening the user intent.\n"
            "5. Before guessing enum values, low-cardinality labels, or real event semantics, use the tools.\n"
            "6. If you truly cannot repair this safely, return sql=null and retryable=false.\n"
            f"{self._schema_tool_guidance(enabled=bool(schema_toolbox))}"
            f"{self._alias_contract_guidance()}"
            f"{self._semantic_catalog_guidance(enabled=semantic_catalog is not None)}"
            '{'
            '"sql":"string|null",'
            '"reason":"string|null",'
            '"retryable":"boolean",'
            '"warnings":["string"]'
            '}'
        )
        user_prompt = json.dumps(
            {
                "today": date.today().isoformat(),
                "dialect": schema.dialect,
                "schema": self._format_schema(schema),
                "semantic_catalog": self._format_semantic_catalog(semantic_catalog),
                "semantic_notes": list(semantic_notes or []),
                "previous_intent": previous_intent_payload,
                "history_text": history_text,
                "alias_contract": self._alias_contract_reference(),
                "available_tools": self._tool_names(schema_toolbox),
                "repair_context": {
                    "user_prompt": prompt,
                    "failed_sql": failed_sql,
                    "failure_reason": failure_reason,
                    "row_count": row_count,
                    "execution_columns": execution_columns or [],
                    "execution_rows_preview": list(execution_rows or [])[:10],
                    "attempt_index": attempt_index,
                },
            },
            ensure_ascii=False,
            indent=2,
        )

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            if schema_toolbox is not None:
                try:
                    content = self._chat_json_with_tools(
                        messages=messages,
                        tools=schema_toolbox.tool_specs(),
                        tool_executor=schema_toolbox.execute_tool,
                        max_rounds=4,
                        max_tokens=1800,
                        temperature=0.0,
                        model=target_model,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("LLM repair tool-call loop failed, falling back to plain repair: %s", exc)
                    content = self._chat_json(
                        messages=messages,
                        max_tokens=1800,
                        temperature=0.0,
                        model=target_model,
                    )
            else:
                content = self._chat_json(
                    messages=messages,
                    max_tokens=1800,
                    temperature=0.0,
                    model=target_model,
                )
            payload = json.loads(self._extract_json_object(content))
            return LLMSqlRepairPayload.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM SQL repair failed: %s", exc)
            return None

    def summarize_result(
        self,
        prompt: str,
        sql: str,
        columns: list[str],
        rows: list[dict[str, Any]],
        row_count: int,
        model: str | None = None,
    ) -> str | None:
        target_model = model or settings.llm_model
        if not self._configured_for_model(target_model) or not rows:
            return None

        try:
            content = self._chat_text(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a BI analyst. Write one short insight in the same language as the user. "
                            "Do not mention SQL. Focus on the most decision-useful takeaway."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "user_prompt": prompt,
                                "sql": sql,
                                "columns": columns,
                                "row_count": row_count,
                                "sample_rows": rows[:10],
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    },
                ],
                max_tokens=220,
                temperature=0.2,
                model=target_model,
            )
            return content.strip() or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM summarization request failed: %s", exc)
            return None

    def suggest_chart(
        self,
        *,
        goal: str,
        sql: str,
        columns: list[dict[str, Any]],
        rows: list[dict[str, Any]],
        row_count: int,
        default_chart: dict[str, Any] | None = None,
        model: str | None = None,
    ) -> LLMChartSuggestionPayload | None:
        target_model = model or settings.llm_model
        if not self._configured_for_model(target_model) or not rows or not columns:
            return None

        system_prompt = (
            "You are a BI chart copilot. "
            "Return exactly one JSON object and no markdown. "
            "You are improving a chart for an already-executed SQL result. "
            "Do not change the SQL or invent columns. "
            "Choose only from supported chart_type values: line, bar, pie, metric_card, table. "
            "Use variant only when needed: single_series, multi_series, grouped, stacked, horizontal_sorted. "
            "Select x_field, y_field, series_field, facet_field only from the provided columns. "
            "Prefer the most dashboard-ready readable chart, but keep it truthful to the result shape. "
            "If the data is too detailed or not suitable for charting, return chart_type='table'. "
            "Return a short human-readable reason and explanation in the same language as the input context.\n"
            "{"
            '"chart_type":"line|bar|pie|metric_card|table",'
            '"variant":"string|null",'
            '"title":"string|null",'
            '"x_field":"string|null",'
            '"y_field":"string|null",'
            '"series_field":"string|null",'
            '"facet_field":"string|null",'
            '"normalize":"none|percent|index_100|running_total|null",'
            '"sort":"string|null",'
            '"reason":"string|null",'
            '"explanation":"string|null",'
            '"confidence":"number|null"'
            "}"
        )
        user_prompt = json.dumps(
            {
                "goal": goal,
                "sql": sql,
                "row_count": row_count,
                "columns": columns,
                "sample_rows": rows[:12],
                "default_chart": default_chart,
            },
            ensure_ascii=False,
            indent=2,
        )

        try:
            content = self._chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1200,
                temperature=0.1,
                model=target_model,
            )
            payload = json.loads(self._extract_json_object(content))
            return LLMChartSuggestionPayload.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM chart suggestion failed: %s", exc)
            return None

    def explain_sql(
        self,
        *,
        sql: str,
        dialect: str | None = None,
        model: str | None = None,
    ) -> SqlExplanationResponse | None:
        target_model = model or settings.llm_model
        if not self._configured_for_model(target_model):
            return self._fallback_sql_explanation(sql, dialect=dialect)

        line_map = self._numbered_sql(sql)
        system_prompt = (
            "You are a senior SQL tutor. "
            "Return exactly one JSON object and no markdown. "
            "Explain the query block by block in the user's language. "
            "The explanation must stay faithful to the SQL and use the original line numbers. "
            "Prefer 3-8 coherent blocks for non-trivial SQL. "
            "If the query is simple, it is fine to produce fewer blocks. "
            "Each block must describe one clause or one logical part of the query and should include the "
            "exact SQL excerpt copied from the source. "
            "Do not invent tables, columns, filters, or business meaning.\n"
            "{"
            '"summary":"string",'
            '"blocks":[{'
            '"index":"number",'
            '"kind":"cte|select|from|join|where|group_by|having|order_by|limit|compound|other",'
            '"title":"string",'
            '"line_start":"number",'
            '"line_end":"number",'
            '"sql":"string",'
            '"explanation":"string"'
            '}],'
            '"warnings":["string"]'
            "}"
        )
        user_prompt = json.dumps(
            {
                "dialect": dialect,
                "sql": sql,
                "numbered_sql": line_map,
            },
            ensure_ascii=False,
            indent=2,
        )

        try:
            content = self._chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=1400,
                temperature=0.1,
                model=str(target_model),
            )
            payload = json.loads(self._extract_json_object(content))
            result = LLMSqlExplanationPayload.model_validate(payload)
            blocks = [SqlExplanationBlock.model_validate(block.model_dump(mode="json")) for block in result.blocks]
            if not blocks:
                return self._fallback_sql_explanation(sql, dialect=dialect)
            return SqlExplanationResponse(
                summary=result.summary.strip(),
                blocks=blocks,
                warnings=[warning.strip() for warning in result.warnings if str(warning).strip()],
                generated_by_ai=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM SQL explanation failed: %s", exc)
            return self._fallback_sql_explanation(sql, dialect=dialect)

    def enrich_semantic_table(
        self,
        table: SemanticTable,
        relationships: list[dict[str, Any]] | None = None,
        join_paths: list[dict[str, Any]] | None = None,
        relationship_graph: list[dict[str, Any]] | None = None,
        database_description: str | None = None,
        model: str | None = None,
    ) -> SemanticTableEnrichment | None:
        target_model = model or settings.llm_model
        if not self._configured_for_model(target_model):
            return None

        column_count = len(table.columns)
        max_tokens = max(1600, 500 + column_count * 180)
        language_hint = self._detect_language(database_description)
        language_rule = {
            "ru": "Все label, business_description и synonyms пиши на русском языке. Используй деловой, но понятный тон.",
            "en": "Write all labels, descriptions and synonyms in English using concise business wording.",
        }.get(language_hint, "Пиши label, business_description и synonyms на русском языке. Если предметная область явно англоязычная, допускается английский, но по умолчанию используй русский деловой стиль.")

        try:
            content = self._chat_json(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты — семантический моделлер данных для BI/аналитики. "
                            "Верни ровно один JSON-объект без markdown и пояснений. "
                            "Задача — улучшить бизнес-лейблы и описания колонок и таблиц, не придумывая новых. "
                            "Нельзя упоминать таблицы/колонки, которых нет во входных данных. "
                            "Запрещено возвращать шаблонные описания вида 'Column X in Y' или 'Physical table X' — "
                            "если не можешь дать осмысленное описание, оставь поле null. "
                            "Используй database_description как главный контекст предметной области. "
                            "Анализируй example_values и имена колонок для вывода семантики. "
                            "Выбирай table_role строго из: fact, dimension, bridge, lookup, event, snapshot. "
                            "Если table_role = fact, grain обязателен и не может быть пустым. "
                            "grain описывай одной короткой фразой (e.g. 'одна строка = один тендер на заказ'). "
                            "important_metrics возвращай как готовые SQL-метрики в формате 'metric_name: SQL_EXPRESSION', а не как простые названия колонок. "
                            "Если у таблицы есть главная дата, main_date_column должен быть физическим именем колонки. "
                            f"{language_rule}"
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "database_description": database_description,
                                "table": table.model_dump(mode="json"),
                                "relationships": relationships or [],
                                "join_paths": join_paths or [],
                                "relationship_graph": relationship_graph or [],
                                "response_shape": {
                                    "table_name": "string",
                                    "label": "string|null",
                                    "business_description": "string|null",
                                    "table_role": "fact|dimension|bridge|lookup|event|snapshot|null",
                                    "grain": "string|null",
                                    "main_date_column": "string|null",
                                    "main_entity": "string|null",
                                    "synonyms": ["string"],
                                    "important_metrics": ["string"],
                                    "important_dimensions": ["string"],
                                    "columns": [
                                        {
                                            "column_name": "string",
                                            "label": "string|null",
                                            "business_description": "string|null",
                                            "semantic_types": ["string"],
                                            "analytics_roles": ["string"],
                                            "synonyms": ["string"],
                                        }
                                    ],
                                },
                            },
                            ensure_ascii=False,
                            indent=2,
                        ),
                    },
                ],
                max_tokens=max_tokens,
                temperature=0.1,
                model=str(target_model),
            )
            payload = json.loads(self._extract_json_object(content))
            payload.setdefault("table_name", table.table_name)
            return SemanticTableEnrichment.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM semantic enrichment failed: %s", exc)
            return None

    def _chat_json(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
        model: str,
    ) -> str:
        response = self._get_client().chat.completions.create(
            model=str(model),
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._extract_text(response.choices[0].message.content)

    def _chat_text(
        self,
        messages: list[dict[str, Any]],
        max_tokens: int,
        temperature: float,
        model: str,
    ) -> str:
        response = self._get_client().chat.completions.create(
            model=str(model),
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._extract_text(response.choices[0].message.content)

    def _chat_json_with_tools(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        tool_executor,
        max_rounds: int,
        max_tokens: int,
        temperature: float,
        model: str,
    ) -> str:
        conversation = [dict(message) for message in messages]
        for _ in range(max_rounds):
            response = self._get_client().chat.completions.create(
                model=str(model),
                messages=conversation,
                tools=tools,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            message = response.choices[0].message
            tool_calls = list(getattr(message, "tool_calls", None) or [])
            assistant_message: dict[str, Any] = {
                "role": "assistant",
                "content": self._extract_text(message.content),
            }
            if tool_calls:
                assistant_message["tool_calls"] = [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": getattr(getattr(call, "function", None), "name", ""),
                            "arguments": getattr(getattr(call, "function", None), "arguments", "{}"),
                        },
                    }
                    for call in tool_calls
                ]
            conversation.append(assistant_message)

            if not tool_calls:
                return assistant_message["content"]

            for call in tool_calls:
                function = getattr(call, "function", None)
                result = tool_executor(
                    getattr(function, "name", ""),
                    getattr(function, "arguments", "{}"),
                )
                conversation.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": json.dumps(result, ensure_ascii=False, indent=2),
                    }
                )

        return self._chat_json(
            messages=[
                *conversation,
                {
                    "role": "system",
                    "content": "Stop using tools. Return the final JSON object now.",
                },
            ],
            max_tokens=max_tokens,
            temperature=temperature,
            model=model,
        )

    def _get_client(self) -> OpenAI:
        if OpenAI is None:
            raise RuntimeError("The 'openai' package is not installed.")
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base_url,
            )
        return self._client

    def _drivee_domain_guidance(self, schema: SchemaMetadataResponse) -> str:
        table = next((item for item in schema.tables if item.name == "train"), None)
        if table is None:
            return ""

        column_names = {column.name for column in table.columns}
        required_columns = {
            "order_timestamp",
            "driveraccept_timestamp",
            "driverarrived_timestamp",
            "driverstarttheride_timestamp",
            "driverdone_timestamp",
            "clientcancel_timestamp",
            "drivercancel_timestamp",
            "cancel_before_accept_local",
            "city_id",
            "driver_id",
            "duration_in_seconds",
            "price_order_local",
            "price_tender_local",
        }
        if not required_columns.issubset(column_names):
            return ""

        return (
            "26. DRIVEE / TRAIN TABLE PLAYBOOK — when the schema contains the single fact table `train` with "
            "lifecycle timestamps, interpret operational ride questions using these event columns: "
            "`order_timestamp` = order created, `driveraccept_timestamp` = driver assigned/accepted, "
            "`driverarrived_timestamp` = driver arrived, `driverstarttheride_timestamp` = ride started, "
            "`driverdone_timestamp` = ride completion event timestamp, `clientcancel_timestamp` = client cancelled, "
            "`drivercancel_timestamp` = driver cancelled, `cancel_before_accept_local` = cancelled before accept. "
            "For the business definition of completed rides/orders, use `status_order = 'done'` unless the user "
            "explicitly asks for completion-event timestamps or says to use `driverdone_timestamp`. "
            "For lifecycle / funnel questions, include stage counts, loss counts between stages, and average plus "
            "p95 durations between stages when those timestamps exist. For assignment-speed questions, measure "
            "`driveraccept_timestamp - order_timestamp`; for arrival-speed questions, measure "
            "`driverarrived_timestamp - driveraccept_timestamp`. For 'time of day' analysis, group by hour "
            "(`DATE_TRUNC('hour', order_timestamp)` or `EXTRACT(HOUR FROM order_timestamp)`), not by calendar date. "
            "For full-cycle questions, split results by final outcome (completed, client_cancelled, "
            "driver_cancelled, cancelled_before_accept) instead of blending all outcomes into one average. "
            "For price-formation questions, compare `price_tender_local` against `price_order_local` using average "
            "delta, average delta percent, and distribution-friendly columns rather than only total sums. "
            "For long unfinished orders followed by 'what do they have in common', produce grouped pattern analysis "
            "over meaningful dimensions instead of returning only raw order rows. For city-comparison questions, "
            "service speed means at least minutes_to_accept and minutes_to_arrival; ride duration alone is not enough.\n"
        )

    def _format_schema(self, schema: SchemaMetadataResponse) -> dict[str, Any]:
        def _column_entry(column: Any) -> dict[str, Any]:
            entry: dict[str, Any] = {"name": column.name, "type": column.type}
            mn = getattr(column, "min_value", None)
            mx = getattr(column, "max_value", None)
            if mn is not None or mx is not None:
                entry["observed_range"] = {"min": mn, "max": mx}
            desc = getattr(column, "description", None)
            if desc:
                entry["description"] = desc
            return entry

        def _table_entry(table: Any) -> dict[str, Any]:
            entry: dict[str, Any] = {
                "table": table.name,
                "columns": [_column_entry(column) for column in table.columns],
            }
            desc = getattr(table, "description", None)
            if desc:
                entry["description"] = desc
            return entry

        return {
            "tables": [_table_entry(table) for table in schema.tables],
            "relationships": [
                {
                    "from_table": relationship.from_table,
                    "from_column": relationship.from_column,
                    "to_table": relationship.to_table,
                    "to_column": relationship.to_column,
                    "relation_type": relationship.relation_type,
                    "cardinality": relationship.cardinality,
                }
                for relationship in schema.relationships
            ],
            "relationship_graph": [
                {
                    "from": edge.from_table,
                    "to": edge.to_table,
                    "on": edge.on,
                }
                for edge in schema.relationship_graph
            ],
        }

    def _format_semantic_catalog(self, catalog: SemanticCatalog | None) -> dict[str, Any] | None:
        if catalog is None:
            return None
        return {
            "tables": [
                {
                    "table_name": table.table_name,
                    "label": table.label,
                    "business_description": table.business_description,
                    "table_role": table.table_role,
                    "grain": table.grain,
                    "main_date_column": table.main_date_column,
                    "main_entity": table.main_entity,
                    "synonyms": list(table.synonyms[:10]),
                    "important_metrics": list(table.important_metrics[:6]),
                    "important_dimensions": list(table.important_dimensions[:8]),
                }
                for table in catalog.tables
            ],
            "join_paths": [
                {
                    "from_table": path.from_table,
                    "to_table": path.to_table,
                    "tables": list(path.tables),
                    "joins": list(path.joins),
                    "business_use_case": path.business_use_case,
                }
                for path in catalog.join_paths
            ],
        }

    def _schema_tool_guidance(self, *, enabled: bool) -> str:
        if not enabled:
            return ""
        return (
            "20. READ-ONLY TOOLING — you may use list_tables, describe_table, sample_rows, and distinct_values. "
            "Use them sparingly when you need real enum values, representative rows, or a clearer join path. "
            "Before asking clarification about status semantics, low-cardinality categories, or concrete labels, "
            "inspect the schema or values via tools. Prefer at most 1–3 tool calls total.\n"
        )

    def _alias_contract_guidance(self) -> str:
        return (
            "21. OUTPUT ALIAS CONTRACT — use stable snake_case aliases. "
            "Time buckets must use the grain as the alias: hour, day, week, month, quarter, year. "
            "Counts must use *_count or total_* (e.g. payment_count, rental_count, total_orders). "
            "Monetary sums must use total_* (e.g. total_revenue). "
            "Ratios, shares, conversion metrics, and late/return percentages must use *_rate. "
            "Average durations must use avg_*_minutes or avg_*_days depending on the unit. "
            "When the request asks for multiple metrics, expose each as its own aliased column.\n"
            "22. FEW-SHOT ALIAS EXAMPLES — "
            "Example A: daily revenue and payment count by store -> columns day, store_id, total_revenue, payment_count. "
            "Example B: top categories by revenue -> columns category, total_revenue. "
            "Example C: weekly average rental days and late return rate -> columns week, avg_rental_days, late_return_rate.\n"
        )

    def _semantic_catalog_guidance(self, *, enabled: bool) -> str:
        if not enabled:
            return ""
        return (
            "23. SEMANTIC CATALOG — when semantic_catalog is provided, treat it as authoritative business context.\n"
            "24. READY-MADE METRICS — prefer important_metrics when they match the request; they already encode business-ready SQL definitions.\n"
            "25. TIME ANCHOR — for temporal filters and time bucketing, prefer each table's main_date_column over guessing another timestamp.\n"
            "26. TABLE ROLES — lookup and bridge tables are helper tables, not the main FROM source for aggregate analytics.\n"
            "27. JOIN PATHS — when semantic_catalog exposes join_paths for the selected tables, follow them instead of inventing a shorter join.\n"
        )

    @staticmethod
    def _few_shot_guidance(*, enabled: bool) -> str:
        if not enabled:
            return ""
        return (
            "FEW-SHOT EXAMPLES — the user_prompt JSON includes a 'few_shot_examples' list of "
            "previously successful {prompt, sql} pairs from this same database. "
            "Use them as reference patterns for table names, join paths, and aggregation idioms. "
            "Adapt (do not copy verbatim) to match the current request.\n"
        )

    def _alias_contract_reference(self) -> dict[str, Any]:
        return {
            "time_buckets": {
                "hour": "hour",
                "day": "day",
                "week": "week",
                "month": "month",
                "quarter": "quarter",
                "year": "year",
            },
            "count_examples": ["payment_count", "rental_count", "total_orders"],
            "sum_examples": ["total_revenue", "total_amount"],
            "rate_examples": ["completion_rate", "conversion_rate", "late_return_rate"],
            "duration_examples": ["avg_pickup_minutes", "avg_rental_days", "avg_ride_minutes"],
        }

    def _tool_names(self, schema_toolbox: "LLMSchemaReconToolbox | None") -> list[str]:
        if schema_toolbox is None:
            return []
        return [
            tool.get("function", {}).get("name")
            for tool in schema_toolbox.tool_specs()
            if tool.get("function", {}).get("name")
        ]

    def _detect_language(self, *texts: str | None) -> str:
        joined = " ".join(text for text in texts if text)
        if not joined:
            return "unknown"
        cyrillic = sum(1 for ch in joined if "\u0400" <= ch <= "\u04FF")
        latin = sum(1 for ch in joined if ("a" <= ch.lower() <= "z"))
        if cyrillic > latin:
            return "ru"
        if latin > 0:
            return "en"
        return "unknown"

    def _extract_json_object(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.DOTALL).strip()
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in LLM response.")
        return match.group(0)

    def _numbered_sql(self, sql: str) -> list[str]:
        lines = sql.splitlines() or [sql]
        return [f"{index + 1}: {line}" for index, line in enumerate(lines)]

    def _fallback_sql_explanation(self, sql: str, dialect: str | None = None) -> SqlExplanationResponse:
        lines = sql.splitlines() or [sql]
        if not lines:
            lines = [sql]

        blocks: list[SqlExplanationBlock] = []
        current_kind: str | None = None
        current_lines: list[tuple[int, str]] = []

        def flush_block() -> None:
            nonlocal current_kind, current_lines
            if not current_lines:
                return
            start = current_lines[0][0]
            end = current_lines[-1][0]
            block_kind = current_kind or "other"
            sql_excerpt = "\n".join(line for _, line in current_lines).strip()
            blocks.append(
                SqlExplanationBlock(
                    index=len(blocks) + 1,
                    kind=block_kind,  # type: ignore[arg-type]
                    title=self._sql_block_title(block_kind),
                    line_start=start,
                    line_end=end,
                    sql=sql_excerpt,
                    explanation=self._sql_block_explanation(block_kind, dialect=dialect),
                )
            )
            current_kind = None
            current_lines = []

        for index, raw_line in enumerate(lines, start=1):
            stripped = raw_line.strip()
            if not stripped and current_lines:
                current_lines.append((index, raw_line))
                continue

            kind = self._detect_sql_block_kind(stripped)
            if current_lines and kind != current_kind and stripped:
                flush_block()

            if not current_lines:
                current_kind = kind
            elif kind != current_kind and stripped:
                current_kind = kind

            current_lines.append((index, raw_line))

        flush_block()

        summary = self._fallback_sql_summary(blocks, dialect=dialect, sql=sql)
        return SqlExplanationResponse(
            summary=summary,
            blocks=blocks,
            warnings=[
                "AI explanation is unavailable, so the query is shown with a structural SQL breakdown."
            ],
            generated_by_ai=False,
        )

    def _detect_sql_block_kind(self, line: str) -> str:
        lowered = line.lower().lstrip(",")
        patterns: list[tuple[str, str]] = [
            (r"^with\b", "cte"),
            (r"^select\b", "select"),
            (r"^from\b", "from"),
            (r"^((left|right|full|inner|cross|outer)\s+)?join\b", "join"),
            (r"^on\b", "join"),
            (r"^where\b", "where"),
            (r"^group\s+by\b", "group_by"),
            (r"^having\b", "having"),
            (r"^order\s+by\b", "order_by"),
            (r"^limit\b", "limit"),
            (r"^(union|except|intersect)\b", "compound"),
        ]
        for pattern, kind in patterns:
            if re.match(pattern, lowered):
                return kind
        if lowered.startswith(")"):
            return "other"
        return "other"

    def _sql_block_title(self, kind: str) -> str:
        titles = {
            "cte": "CTE / временный подзапрос",
            "select": "Выборка полей",
            "from": "Основная таблица",
            "join": "Соединение таблиц",
            "where": "Фильтрация строк",
            "group_by": "Группировка",
            "having": "Фильтр по агрегатам",
            "order_by": "Сортировка",
            "limit": "Ограничение результата",
            "compound": "Объединение запросов",
            "other": "Прочая логика",
        }
        return titles.get(kind, titles["other"])

    def _sql_block_explanation(self, kind: str, *, dialect: str | None = None) -> str:
        suffix = f" для {dialect}" if dialect else ""
        explanations = {
            "cte": "Объявляет промежуточный набор данных, чтобы упростить основной запрос.",
            "select": "Перечисляет поля и вычисления, которые попадут в итоговый результат.",
            "from": "Задаёт базовую таблицу или подзапрос, от которого строится запрос.",
            "join": "Подключает связанную таблицу и расширяет набор данных дополнительными полями.",
            "where": "Отсекает строки до группировки и агрегации.",
            "group_by": "Собирает строки в группы по выбранным измерениям.",
            "having": "Фильтрует уже сгруппированные данные по агрегатам.",
            "order_by": "Упорядочивает готовый результат по одному или нескольким полям.",
            "limit": "Ограничивает число возвращаемых строк.",
            "compound": "Объединяет несколько запросов в один результат.",
            "other": "Поддерживает основную логику запроса или содержит служебное выражение.",
        }
        return f"{explanations.get(kind, explanations['other'])}{suffix}."

    def _fallback_sql_summary(self, blocks: list[SqlExplanationBlock], *, dialect: str | None = None, sql: str) -> str:
        if not blocks:
            return "SQL query could not be split into blocks, but the raw text is available below."
        if len(blocks) == 1:
            return "Запрос состоит из одного логического блока, поэтому он показан как единая последовательность."
        dialect_suffix = f" для {dialect}" if dialect else ""
        return f"Запрос разбит на {len(blocks)} логических блоков{dialect_suffix}, чтобы было проще понять его структуру."

    def _extract_text(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
                else:
                    text = getattr(item, "text", None)
                    if text:
                        parts.append(str(text))
            return "\n".join(parts).strip()
        return str(content or "")
