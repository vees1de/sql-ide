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
        return bool(
            OpenAI is not None
            and settings.llm_api_base_url
            and settings.llm_api_key
            and settings.llm_model
        )

    def plan_query(
        self,
        prompt: str,
        schema: SchemaMetadataResponse,
        previous_intent: IntentPayload | None = None,
        history_text: str | None = None,
        temperature: float = 0.1,
    ) -> LLMQueryPlan | None:
        if not self.configured:
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
            "Return this JSON shape:\n"
            "{"
            '"intent":{"raw_prompt":"string","metric":"string|null","dimensions":["string"],'
            '"filters":[{"field":"string","operator":"string","value":"any"}],'
            '"comparison":"string|null","date_range":{"kind":"absolute|relative","start":"YYYY-MM-DD|null",'
            '"end":"YYYY-MM-DD|null","lookback_value":"number|null","lookback_unit":"string|null"}|null,'
            '"visualization_preference":"line|bar|pie|table|null","ambiguities":["string"],'
            '"clarification_question":"string|null","confidence":"number","follow_up":"boolean"},'
            '"sql":"string|null","chart_type":"line|bar|pie|table|null","chart_x_field":"string|null",'
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
    ) -> str | None:
        if not self.configured or not rows:
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
            )
            return content.strip() or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM summarization request failed: %s", exc)
            return None

    def _chat_json(self, messages: list[dict[str, str]], max_tokens: int, temperature: float) -> str:
        response = self._get_client().chat.completions.create(
            model=str(settings.llm_model),
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return self._extract_text(response.choices[0].message.content)

    def _chat_text(self, messages: list[dict[str, str]], max_tokens: int, temperature: float) -> str:
        response = self._get_client().chat.completions.create(
            model=str(settings.llm_model),
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
        return {
            "tables": [
                {
                    "table": table.name,
                    "columns": [{"name": column.name, "type": column.type} for column in table.columns],
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
