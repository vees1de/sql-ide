from __future__ import annotations

import json
import logging
import re
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings
from app.schemas.metadata import SchemaMetadataResponse
from app.schemas.query import IntentPayload
from app.schemas.semantic_catalog import SemanticTable, SemanticTableEnrichment

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - runtime optional dependency
    OpenAI = None


logger = logging.getLogger(__name__)


class LLMQueryPlan(BaseModel):
    intent: IntentPayload
    sql: str | None = None
    chart_type: str | None = None
    chart_x_field: str | None = None
    chart_y_field: str | None = None
    chart_title: str | None = None
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
        previous_intent: IntentPayload | None = None,
        history_text: str | None = None,
        temperature: float = 0.1,
        model: str | None = None,
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
            "and generate a single safe read-only SELECT query when possible.\n"
            "Rules:\n"
            "1. Use only tables, columns, and relationships from the schema.\n"
            "2. Never generate INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, COPY, GRANT or transaction statements.\n"
            "3. Prefer explicit JOINs and explicit aliases.\n"
            "4. Keep SQL compatible with the provided SQL dialect.\n"
            "5. If the request is ambiguous, set intent.clarification_question and return sql as null.\n"
            "6. Keep warnings concise.\n"
            "7. Match the user's language in clarification text.\n"
            "8. Use conversation history when provided to resolve follow-up intent.\n"
            "9. Prefer join paths that are present in relationship_graph when choosing table traversal.\n"
            "10. When you set clarification_question, ALSO populate clarification_options with 3–5 concrete, "
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
            "17. CHART TYPE SELECTION — always set chart_type to the most useful visualization, even "
            "when the user did not explicitly request one. Rules for proactive chart selection:\n"
            "  (a) EXPLICIT REQUEST — if the user explicitly names a chart type in any language, honor it: "
            "'столбчатую диаграмму'/'bar chart'/'bar' → 'bar'; "
            "'круговую'/'pie'/'распределение' → 'pie'; "
            "'линейный'/'line'/'график'/'trend' → 'line'.\n"
            "  (b) DISTRIBUTION / CATEGORICAL BREAKDOWN — when the query groups by a low-cardinality "
            "categorical column (foot, position, country, status) and the user asks for 'распределение', "
            "'доля', 'breakdown', 'proportion', or similar → use 'pie'.\n"
            "  (c) TIME SERIES / TREND — when the result is grouped by a date/time column or the user "
            "asks 'по годам', 'по месяцам', 'динамика', 'менялся', 'со временем', 'trend', 'over time' "
            "→ use 'line'.\n"
            "  (d) RANKING / TOP-N / COMPARISON — when the query ranks entities, finds top/best/worst, "
            "or compares named items across a numeric metric → use 'bar'.\n"
            "  (e) SCALAR — when the result is a single number (no GROUP BY) → use 'metric_card'.\n"
            "  (f) FALLBACK — use 'table' only when none of the above apply or the result is inherently "
            "multi-dimensional. Never leave chart_type null unless you truly cannot determine a useful type.\n"
            "  Set chart_x_field and chart_y_field accordingly: x = the dimension column, y = the numeric metric column.\n"
            "{"
            '"intent":{"raw_prompt":"string","metric":"string|null","dimensions":["string"],'
            '"filters":[{"field":"string","operator":"string","value":"any"}],'
            '"comparison":"string|null","date_range":{"kind":"absolute|relative","start":"YYYY-MM-DD|null",'
            '"end":"YYYY-MM-DD|null","lookback_value":"number|null","lookback_unit":"string|null"}|null,'
            '"visualization_preference":"line|bar|pie|table|null","ambiguities":["string"],'
            '"clarification_question":"string|null",'
            '"clarification_options":[{"id":"string","label":"string","detail":"string|null","reason":"string|null"}],'
            '"confidence":"number","follow_up":"boolean"},'
            '"sql":"string|null","chart_type":"line|bar|pie|table|metric_card|null","chart_x_field":"string|null",'
            '"chart_y_field":"string|null","chart_title":"string|null","warnings":["string"]}'
        )
        user_prompt = json.dumps(
            {
                "today": date.today().isoformat(),
                "dialect": schema.dialect,
                "schema": schema_summary,
                "previous_intent": previous_intent_payload,
                "history_text": history_text,
                "user_prompt": prompt,
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
                temperature=temperature,
                model=target_model,
            )
            payload = json.loads(self._extract_json_object(content))
            payload.setdefault("intent", {})
            payload["intent"].setdefault("raw_prompt", prompt)
            return LLMQueryPlan.model_validate(payload)
        except (ValidationError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Failed to parse LLM query plan: %s", exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM planning request failed: %s", exc)
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

        try:
            content = self._chat_json(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a semantic data modeler. "
                            "Return exactly one JSON object and no markdown. "
                            "Your task is to improve business labels and descriptions without inventing new columns. "
                            "Never reference tables or columns that are not present in the input. "
                            "Prefer conservative updates over speculative ones. "
                            "If a database-level description is provided, use it as the highest-level context for naming "
                            "tables, columns, roles, and business descriptions."
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
                max_tokens=1200,
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
        messages: list[dict[str, str]],
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
        messages: list[dict[str, str]],
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

    def _get_client(self) -> OpenAI:
        if OpenAI is None:
            raise RuntimeError("The 'openai' package is not installed.")
        if self._client is None:
            self._client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.llm_api_base_url,
            )
        return self._client

    def _format_schema(self, schema: SchemaMetadataResponse) -> dict[str, Any]:
        def _column_entry(column: Any) -> dict[str, Any]:
            entry: dict[str, Any] = {"name": column.name, "type": column.type}
            mn = getattr(column, "min_value", None)
            mx = getattr(column, "max_value", None)
            if mn is not None or mx is not None:
                entry["observed_range"] = {"min": mn, "max": mx}
            return entry

        return {
            "tables": [
                {
                    "table": table.name,
                    "columns": [_column_entry(column) for column in table.columns],
                }
                for table in schema.tables
            ],
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

    def _extract_json_object(self, content: str) -> str:
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.DOTALL).strip()
        match = re.search(r"\{.*\}", stripped, flags=re.DOTALL)
        if not match:
            raise ValueError("No JSON object found in LLM response.")
        return match.group(0)

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
