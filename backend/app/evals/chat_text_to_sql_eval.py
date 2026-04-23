from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import sqlglot
from pydantic import BaseModel, Field
from sqlglot import expressions as exp

from app.core.config import normalize_llm_model_alias, resolve_llm_model_from_alias, settings
from app.schemas.query import QueryMode

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional at runtime
    OpenAI = None


ISSUE_HINTS: dict[str, dict[str, Any]] = {
    "clarification_expected": {
        "summary": "Модель не запросила уточнение в неоднозначном кейсе.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/intent.py",
            "backend/app/agents/clarification.py",
            "backend/app/services/chat_sql_adapter.py",
        ],
    },
    "clarification_unexpected": {
        "summary": "Модель уходит в уточнение там, где ожидался прямой SQL-ответ.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/intent.py",
            "backend/app/services/chat_sql_adapter.py",
        ],
    },
    "clarification_question_terms_missing": {
        "summary": "Уточняющий вопрос сформулирован слишком расплывчато или не попадает в нужную развилку.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/clarification.py",
        ],
    },
    "clarification_options_missing": {
        "summary": "Варианты уточнения слишком бедные, не schema-grounded или не покрывают нужные ответы.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/clarification.py",
        ],
    },
    "metric_mismatch": {
        "summary": "LLM неверно поняла, какую метрику надо считать.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/intent.py",
            "backend/app/agents/semantic.py",
        ],
    },
    "dimension_missing": {
        "summary": "LLM потеряла нужную группировку или не сохранила контекст follow-up запроса.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/intent.py",
            "backend/app/agents/semantic.py",
            "backend/app/services/chat_sql_adapter.py",
        ],
    },
    "filter_missing": {
        "summary": "Фильтр по строкам/срезу не дошёл до intent или SQL.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/intent.py",
            "backend/app/agents/semantic.py",
            "backend/app/services/chat_sql_adapter.py",
        ],
    },
    "date_range_mismatch": {
        "summary": "Неверно распознан период или он не перенесён в запрос.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/intent.py",
            "backend/app/agents/sql_generation.py",
            "backend/app/services/schema_context_provider.py",
        ],
    },
    "sql_missing": {
        "summary": "SQL вообще не был сгенерирован там, где ожидался ответ.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/services/chat_sql_adapter.py",
            "backend/app/services/analytics_agent_service.py",
        ],
    },
    "sql_parse_error": {
        "summary": "Сгенерированный SQL синтаксически ненадёжен.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/sql_generation.py",
            "backend/app/agents/validation.py",
        ],
    },
    "sql_required_substring_missing": {
        "summary": "В SQL отсутствует критичный паттерн: LIMIT, GROUP BY, агрегация, нужный predicate.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/sql_generation.py",
            "backend/app/agents/semantic.py",
        ],
    },
    "sql_forbidden_substring_present": {
        "summary": "В SQL появился нежелательный паттерн, который ведёт к неверной логике или риску.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/sql_generation.py",
            "backend/app/agents/validation.py",
        ],
    },
    "sql_table_missing": {
        "summary": "SQL не использует ожидаемую таблицу или не делает нужный join.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/semantic.py",
            "backend/app/agents/sql_generation.py",
        ],
    },
    "sql_forbidden_table_present": {
        "summary": "SQL опирается на лишнюю или подозрительную таблицу.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/semantic.py",
            "backend/app/agents/validation.py",
        ],
    },
    "sql_column_missing": {
        "summary": "В SQL не попали нужные колонки/алиасы.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/semantic.py",
            "backend/app/agents/sql_generation.py",
        ],
    },
    "execution_missing": {
        "summary": "Тестер не получил execution payload, хотя он нужен для проверки результата.",
        "files": [
            "backend/app/api/routes/chat.py",
            "backend/app/services/chat_execution_service.py",
        ],
    },
    "execution_failed": {
        "summary": "SQL доехал до execution, но упал на реальной БД.",
        "files": [
            "backend/app/services/chat_execution_service.py",
            "backend/app/agents/validation.py",
            "backend/app/services/llm_service.py",
            "backend/app/agents/sql_generation.py",
        ],
    },
    "execution_row_count_low": {
        "summary": "SQL формально выполняется, но возвращает слишком мало строк для ожидаемого среза.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/semantic.py",
            "backend/app/agents/sql_generation.py",
        ],
    },
    "execution_row_count_high": {
        "summary": "SQL возвращает слишком много строк, вероятно потерян LIMIT или агрегация.",
        "files": [
            "backend/app/services/llm_service.py",
            "backend/app/agents/sql_generation.py",
            "backend/app/agents/validation.py",
        ],
    },
    "execution_required_column_missing": {
        "summary": "Результат не содержит ожидаемых полей для таблицы/чарта.",
        "files": [
            "backend/app/agents/sql_generation.py",
            "backend/app/services/chat_execution_service.py",
            "backend/app/services/chart_data_adapter.py",
        ],
    },
    "chart_missing": {
        "summary": "Chart recommendation отсутствует или не может быть построен.",
        "files": [
            "backend/app/services/chart_decision_service.py",
            "backend/app/services/chart_data_adapter.py",
            "backend/app/services/chat_execution_service.py",
        ],
    },
    "chart_type_mismatch": {
        "summary": "Выбран неподходящий тип графика.",
        "files": [
            "backend/app/services/chart_decision_service.py",
            "backend/app/services/chart_data_adapter.py",
            "backend/app/services/llm_service.py",
        ],
    },
    "chart_x_mismatch": {
        "summary": "Неверно выбрана ось X.",
        "files": [
            "backend/app/services/chart_decision_service.py",
            "backend/app/services/chart_data_adapter.py",
        ],
    },
    "chart_y_mismatch": {
        "summary": "Неверно выбрана метрика на оси Y.",
        "files": [
            "backend/app/services/chart_decision_service.py",
            "backend/app/services/chart_data_adapter.py",
        ],
    },
    "chart_series_mismatch": {
        "summary": "Серия/legend выбрана неверно либо потеряна.",
        "files": [
            "backend/app/services/chart_decision_service.py",
            "backend/app/services/chart_data_adapter.py",
        ],
    },
}


class FilterExpectation(BaseModel):
    field: str
    operator: str | None = None
    value: Any | None = None
    value_any_of: list[Any] = Field(default_factory=list)
    value_contains: list[str] = Field(default_factory=list)


class DateRangeExpectation(BaseModel):
    kind: str | None = None
    start: date | None = None
    end: date | None = None
    lookback_value: int | None = None
    lookback_unit: str | None = None


class ClarificationExpectation(BaseModel):
    question_should_contain: list[str] = Field(default_factory=list)
    options_should_include: list[str] = Field(default_factory=list)
    min_options: int = 0


class InterpretationExpectation(BaseModel):
    metric_any_of: list[str] = Field(default_factory=list)
    dimensions_all_of: list[str] = Field(default_factory=list)
    dimensions_any_of: list[str] = Field(default_factory=list)
    filters: list[FilterExpectation] = Field(default_factory=list)
    date_range: DateRangeExpectation | None = None


class SQLExpectation(BaseModel):
    must_parse: bool = True
    required_substrings: list[str] = Field(default_factory=list)
    forbidden_substrings: list[str] = Field(default_factory=list)
    required_tables: list[str] = Field(default_factory=list)
    forbidden_tables: list[str] = Field(default_factory=list)
    required_columns: list[str] = Field(default_factory=list)


class ChartExpectation(BaseModel):
    acceptable_types: list[str] = Field(default_factory=list)
    acceptable_views: list[str] = Field(default_factory=list)
    x_any_of: list[str] = Field(default_factory=list)
    y_any_of: list[str] = Field(default_factory=list)
    series_any_of: list[str] = Field(default_factory=list)


class ExecutionExpectation(BaseModel):
    should_succeed: bool | None = True
    min_row_count: int | None = None
    max_row_count: int | None = None
    required_columns_all_of: list[str] = Field(default_factory=list)
    required_column_groups: list[list[str]] = Field(default_factory=list)
    chart: ChartExpectation | None = None


class StepExpectations(BaseModel):
    should_clarify: bool | None = None
    expected_state: str | None = None
    required_actions: list[str] = Field(default_factory=list)
    clarification: ClarificationExpectation | None = None
    interpretation: InterpretationExpectation | None = None
    sql: SQLExpectation | None = None
    execution: ExecutionExpectation | None = None


class ConversationStepSpec(BaseModel):
    user: str
    query_mode: QueryMode | None = None
    llm_model_alias: str | None = None
    execute_sql: bool | None = None
    clarification_reply: str | None = None
    max_auto_clarifications: int = 2
    expectations: StepExpectations = Field(default_factory=StepExpectations)


class ConversationCaseSpec(BaseModel):
    id: str
    title: str | None = None
    tags: list[str] = Field(default_factory=list)
    database_id: str | None = None
    database_name: str | None = None
    steps: list[ConversationStepSpec]


class EvalSuiteSpec(BaseModel):
    suite_name: str = "chat_text_to_sql"
    database_id: str | None = None
    database_name: str | None = None
    query_mode: QueryMode = "thinking"
    llm_model_alias: str | None = None
    cases: list[ConversationCaseSpec]


@dataclass
class CheckOutcome:
    bucket: str
    code: str
    passed: bool
    score: float
    weight: float
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "bucket": self.bucket,
            "code": self.code,
            "passed": self.passed,
            "score": round(self.score, 4),
            "weight": self.weight,
            "message": self.message,
        }


class ChatEvalApiClient:
    def __init__(self, api_base: str, timeout_seconds: int = 180) -> None:
        self.api_base = api_base.rstrip("/")
        self.client = httpx.Client(base_url=self.api_base, timeout=timeout_seconds)

    def close(self) -> None:
        self.client.close()

    def list_databases(self) -> list[dict[str, Any]]:
        response = self.client.get("chat/databases")
        response.raise_for_status()
        return list(response.json())

    def create_session(self, database_id: str, title: str) -> dict[str, Any]:
        response = self.client.post(f"chat/databases/{database_id}/sessions", json={"title": title})
        response.raise_for_status()
        return dict(response.json())

    def send_message(
        self,
        session_id: str,
        text: str,
        query_mode: QueryMode,
        llm_model_alias: str | None,
    ) -> dict[str, Any]:
        payload = {
            "text": text,
            "query_mode": query_mode,
            "llm_model_alias": llm_model_alias,
        }
        response = self.client.post(f"chat/sessions/{session_id}/messages", json=payload)
        response.raise_for_status()
        return dict(response.json())

    def execute_sql(self, session_id: str, sql: str) -> dict[str, Any]:
        response = self.client.post(f"chat/sessions/{session_id}/execute", json={"sql": sql})
        response.raise_for_status()
        return dict(response.json())


class OptionalLLMJudge:
    def __init__(self, *, enabled: bool, model_alias: str | None = None) -> None:
        self.enabled = enabled
        self.model_alias = normalize_llm_model_alias(model_alias) if model_alias else None
        self._client: OpenAI | None = None

    @property
    def available(self) -> bool:
        if not self.enabled:
            return False
        return bool(OpenAI is not None and settings.llm_api_base_url and settings.llm_api_key)

    def _client_instance(self) -> OpenAI:
        if self._client is None:
            if OpenAI is None:
                raise RuntimeError("openai package is not installed")
            self._client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_api_base_url)
        return self._client

    def judge_step(
        self,
        *,
        prompt: str,
        expectations: StepExpectations,
        actual: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not self.available:
            return None

        model = resolve_llm_model_from_alias(self.model_alias) if self.model_alias else settings.llm_model
        if not model:
            return None

        system_prompt = (
            "You are evaluating a chat text-to-SQL system. "
            "Return exactly one JSON object and no markdown. "
            "Score each bucket from 0.0 to 1.0 using the provided expectations only. "
            "Use `understanding_score`, `sql_score`, `chart_score`, `overall_score`. "
            "Add `issues` as a short list of concrete failure notes. "
            "Add `repair_hints` as short actionable engineering directions. "
            "If a bucket is not applicable, still return a score and keep it neutral at 1.0."
        )
        user_payload = {
            "prompt": prompt,
            "expectations": expectations.model_dump(mode="json"),
            "actual": actual,
        }

        try:
            response = self._client_instance().chat.completions.create(
                model=model,
                temperature=0.0,
                max_tokens=700,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": json.dumps(user_payload, ensure_ascii=False, indent=2),
                    },
                ],
            )
            raw = response.choices[0].message.content or ""
            return json.loads(_extract_json_object(raw))
        except Exception as exc:  # noqa: BLE001
            return {"judge_error": str(exc)}


class ChatTextToSqlEvaluator:
    def __init__(
        self,
        api_base: str,
        *,
        default_query_mode: QueryMode = "thinking",
        default_model_alias: str | None = None,
        judge: OptionalLLMJudge | None = None,
    ) -> None:
        self.api = ChatEvalApiClient(api_base)
        self.default_query_mode = default_query_mode
        self.default_model_alias = normalize_llm_model_alias(default_model_alias) if default_model_alias else None
        self.judge = judge or OptionalLLMJudge(enabled=False)

    def close(self) -> None:
        self.api.close()

    def run_suite(
        self,
        suite: EvalSuiteSpec,
        *,
        database_id_override: str | None = None,
        database_name_override: str | None = None,
        query_mode_override: QueryMode | None = None,
        model_alias_override: str | None = None,
    ) -> dict[str, Any]:
        started_at = datetime.now(timezone.utc)
        databases = self.api.list_databases()
        case_results: list[dict[str, Any]] = []

        for case in suite.cases:
            database = self._resolve_database(
                databases=databases,
                database_id=database_id_override or case.database_id or suite.database_id,
                database_name=database_name_override or case.database_name or suite.database_name,
            )
            case_results.append(
                self._run_case(
                    case,
                    database=database,
                    query_mode=query_mode_override or suite.query_mode or self.default_query_mode,
                    model_alias=model_alias_override or case.steps[0].llm_model_alias or suite.llm_model_alias or self.default_model_alias,
                )
            )

        finished_at = datetime.now(timezone.utc)
        summary = _build_suite_summary(
            suite_name=suite.suite_name,
            api_base=self.api.api_base,
            case_results=case_results,
            started_at=started_at,
            finished_at=finished_at,
            judge_used=self.judge.available,
        )
        return {
            "suite": suite.model_dump(mode="json"),
            "summary": summary,
            "cases": case_results,
            "repair_targets": _build_repair_targets(case_results),
        }

    def _resolve_database(
        self,
        *,
        databases: list[dict[str, Any]],
        database_id: str | None,
        database_name: str | None,
    ) -> dict[str, Any]:
        if database_id:
            for item in databases:
                if item.get("id") == database_id:
                    return item
            raise ValueError(f"Database id '{database_id}' not found.")
        if database_name:
            for item in databases:
                if _normalize_text(item.get("name")) == _normalize_text(database_name):
                    return item
            raise ValueError(f"Database name '{database_name}' not found.")
        if not databases:
            raise ValueError("No databases returned by /chat/databases.")
        return databases[0]

    def _run_case(
        self,
        case: ConversationCaseSpec,
        *,
        database: dict[str, Any],
        query_mode: QueryMode,
        model_alias: str | None,
    ) -> dict[str, Any]:
        session = self.api.create_session(database["id"], f"eval::{case.id}")
        step_results: list[dict[str, Any]] = []

        for index, step in enumerate(case.steps, start=1):
            resolved_query_mode = step.query_mode or query_mode
            resolved_model_alias = normalize_llm_model_alias(step.llm_model_alias or model_alias) if (step.llm_model_alias or model_alias) else None
            initial_send_payload = self.api.send_message(
                session_id=session["id"],
                text=step.user,
                query_mode=resolved_query_mode,
                llm_model_alias=resolved_model_alias,
            )
            send_payload = initial_send_payload
            clarification_transcript: list[dict[str, Any]] = []

            for clarification_round in range(max(step.max_auto_clarifications, 0)):
                if not _needs_clarification(send_payload):
                    break
                answer = _resolve_clarification_answer(send_payload, preferred_reply=step.clarification_reply)
                if not answer:
                    break
                clarification_transcript.append(
                    {
                        "round": clarification_round + 1,
                        "question": _structured_payload(send_payload).get("clarification_question"),
                        "answer": answer,
                        "options": _structured_payload(send_payload).get("clarification_options") or [],
                    }
                )
                send_payload = self.api.send_message(
                    session_id=session["id"],
                    text=answer,
                    query_mode=resolved_query_mode,
                    llm_model_alias=resolved_model_alias,
                )

            actual_sql = _extract_sql(send_payload)
            needs_clarification = _needs_clarification(send_payload)
            should_execute = (
                step.execute_sql
                if step.execute_sql is not None
                else bool(actual_sql and not needs_clarification and step.expectations.execution is not None)
            )
            if step.expectations.execution is not None and actual_sql and not needs_clarification:
                should_execute = True
            execution_payload = self.api.execute_sql(session["id"], actual_sql) if (should_execute and actual_sql) else None

            # Item 3: SQL self-repair loop — up to 2 retries on execution error or empty result
            repair_transcript: list[dict[str, Any]] = []
            if resolved_query_mode == "thinking" and actual_sql and execution_payload:
                expects_rows = (
                    step.expectations.execution is not None
                    and (step.expectations.execution.min_row_count or 0) > 0
                )
                for _repair_round in range(2):
                    exec_result = execution_payload.get("execution") or {}
                    error_msg = exec_result.get("error_message")
                    row_count = int(exec_result.get("row_count") or 0)
                    if not error_msg and not (expects_rows and row_count == 0):
                        break
                    if error_msg:
                        repair_text = f"SQL вернул ошибку: {error_msg}. Пожалуйста, исправь запрос, не меняя бизнес-логику."
                    else:
                        repair_text = (
                            "SQL выполнился, но вернул 0 строк. "
                            "Скорее всего, фильтр слишком строгий или содержит неверное значение. "
                            "Проверь фильтры и исправь запрос."
                        )
                    repair_send = self.api.send_message(
                        session_id=session["id"],
                        text=repair_text,
                        query_mode=resolved_query_mode,
                        llm_model_alias=resolved_model_alias,
                    )
                    repaired_sql = _extract_sql(repair_send)
                    repair_transcript.append({
                        "round": _repair_round + 1,
                        "trigger": error_msg or "empty_result",
                        "repair_prompt": repair_text,
                        "repaired_sql": repaired_sql,
                    })
                    if repaired_sql and repaired_sql != actual_sql:
                        send_payload = repair_send
                        actual_sql = repaired_sql
                        execution_payload = self.api.execute_sql(session["id"], actual_sql)
                    else:
                        break

            step_result = evaluate_step(
                case_id=case.id,
                step_index=index,
                database=database,
                user_prompt=step.user,
                query_mode=resolved_query_mode,
                llm_model_alias=resolved_model_alias,
                expectations=step.expectations,
                initial_send_payload=initial_send_payload,
                final_send_payload=send_payload,
                clarification_transcript=clarification_transcript,
                execution_payload=execution_payload,
            )
            if repair_transcript:
                step_result["repair_transcript"] = repair_transcript

            # Item 4: blend judge score into overall when --with-judge is active
            if self.judge.enabled:
                judge_result = self.judge.judge_step(
                    prompt=step.user,
                    expectations=step.expectations,
                    actual=step_result["actual"],
                )
                step_result["llm_judge"] = judge_result
                if judge_result and isinstance(judge_result.get("overall_score"), (int, float)):
                    rule_score = step_result["scores"].get("overall", 0.0)
                    judge_score = float(judge_result["overall_score"])
                    step_result["scores"]["overall_rule_based"] = rule_score
                    step_result["scores"]["overall_judge"] = round(judge_score, 4)
                    step_result["scores"]["overall"] = round(0.5 * rule_score + 0.5 * judge_score, 4)
            step_results.append(step_result)

        scores = _aggregate_case_scores(step_results)
        issue_counts = dict(Counter(check["code"] for step in step_results for check in step["checks"] if not check["passed"]))
        return {
            "case_id": case.id,
            "title": case.title or case.id,
            "tags": list(case.tags),
            "database": {
                "id": database.get("id"),
                "name": database.get("name"),
                "dialect": database.get("dialect"),
            },
            "session_id": session["id"],
            "scores": scores,
            "issue_counts": issue_counts,
            "steps": step_results,
        }


def evaluate_step(
    *,
    case_id: str,
    step_index: int,
    database: dict[str, Any],
    user_prompt: str,
    query_mode: QueryMode,
    llm_model_alias: str | None,
    expectations: StepExpectations,
    initial_send_payload: dict[str, Any],
    final_send_payload: dict[str, Any],
    clarification_transcript: list[dict[str, Any]],
    execution_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    initial_structured = _structured_payload(initial_send_payload)
    final_structured = _structured_payload(final_send_payload)
    structured = final_structured or initial_structured
    actual_intent = _actual_intent(final_send_payload, structured)
    actual_sql = _extract_sql(final_send_payload)
    actual_execution = (execution_payload or {}).get("execution") or {}
    actual_chart = actual_execution.get("chart_recommendation") or {}
    actual = {
        "database": {
            "id": database.get("id"),
            "name": database.get("name"),
            "dialect": database.get("dialect"),
        },
        "needs_clarification": _needs_clarification(initial_send_payload),
        "state": structured.get("state"),
        "actions": [str((action or {}).get("type") or "") for action in (structured.get("actions") or [])],
        "clarification_question": initial_structured.get("clarification_question"),
        "clarification_options": initial_structured.get("clarification_options") or [],
        "message_kind": structured.get("message_kind"),
        "initial_message_kind": initial_structured.get("message_kind"),
        "clarification_transcript": clarification_transcript,
        "intent": actual_intent,
        "sql": actual_sql,
        "execution": actual_execution or None,
        "chart": actual_chart or None,
    }
    checks: list[CheckOutcome] = []

    checks.extend(_evaluate_understanding(expectations, actual))
    checks.extend(_evaluate_sql(expectations, actual))
    checks.extend(_evaluate_execution_and_chart(expectations, actual))

    score_payload = _bucket_score_payload(checks)
    return {
        "case_id": case_id,
        "step_index": step_index,
        "step_ref": f"{case_id}#step{step_index}",
        "user_prompt": user_prompt,
        "query_mode": query_mode,
        "llm_model_alias": llm_model_alias,
        "expectations": expectations.model_dump(mode="json"),
        "actual": actual,
        "scores": score_payload["scores"],
        "applicable_buckets": score_payload["applicable_buckets"],
        "checks": [check.as_dict() for check in checks],
    }


def _evaluate_understanding(expectations: StepExpectations, actual: dict[str, Any]) -> list[CheckOutcome]:
    checks: list[CheckOutcome] = []
    actual_needs_clarification = bool(actual.get("needs_clarification"))
    actual_intent = actual.get("intent") or {}

    if expectations.should_clarify is not None:
        if actual_needs_clarification == expectations.should_clarify:
            checks.append(CheckOutcome("understanding", "clarification_match", True, 1.0, 2.0, "Clarification expectation matched."))
        elif expectations.should_clarify:
            checks.append(CheckOutcome("understanding", "clarification_expected", False, 0.0, 2.0, "Expected a clarification question, but the system tried to answer directly."))
        else:
            checks.append(CheckOutcome("understanding", "clarification_unexpected", False, 0.0, 2.0, "Expected a direct answer, but the system asked for clarification."))

    if expectations.expected_state:
        actual_state = str(actual.get("state") or "")
        checks.append(
            CheckOutcome(
                "understanding",
                "state_match" if actual_state == expectations.expected_state else "state_mismatch",
                actual_state == expectations.expected_state,
                1.0 if actual_state == expectations.expected_state else 0.0,
                1.0,
                f"Expected state {expectations.expected_state}, got {actual_state or 'none'}.",
            )
        )

    if expectations.required_actions:
        actual_actions = {str(item) for item in actual.get("actions") or []}
        missing_actions = [action for action in expectations.required_actions if action not in actual_actions]
        checks.append(
            CheckOutcome(
                "understanding",
                "actions_match" if not missing_actions else "actions_missing",
                not missing_actions,
                1.0 if not missing_actions else 0.0,
                1.0,
                "All required actions are present." if not missing_actions else f"Missing actions: {', '.join(missing_actions)}.",
            )
        )

    clarification = expectations.clarification
    if clarification is not None:
        options = actual.get("clarification_options") or []
        question = str(actual.get("clarification_question") or "")
        if not actual_needs_clarification:
            checks.append(CheckOutcome("understanding", "clarification_question_terms_missing", False, 0.0, 1.0, "No clarification payload returned."))
        else:
            if clarification.min_options:
                passed = len(options) >= clarification.min_options
                checks.append(
                    CheckOutcome(
                        "understanding",
                        "clarification_options_count",
                        passed,
                        1.0 if passed else 0.0,
                        1.0,
                        f"Clarification options: {len(options)} (expected at least {clarification.min_options}).",
                    )
                )
            if clarification.question_should_contain:
                matched = _contains_any(question, clarification.question_should_contain)
                checks.append(
                    CheckOutcome(
                        "understanding",
                        "clarification_question_terms_missing" if not matched else "clarification_question_terms_match",
                        matched,
                        1.0 if matched else 0.0,
                        1.0,
                        f"Clarification question: {question or '∅'}",
                    )
                )
            if clarification.options_should_include:
                missing_terms = [
                    term for term in clarification.options_should_include
                    if not any(_contains(option.get("label"), term) or _contains(option.get("detail"), term) for option in options)
                ]
                passed = not missing_terms
                checks.append(
                    CheckOutcome(
                        "understanding",
                        "clarification_options_missing" if not passed else "clarification_options_match",
                        passed,
                        1.0 if passed else 0.0,
                        1.0,
                        "Missing clarification option terms: " + ", ".join(missing_terms) if missing_terms else "Clarification options cover expected branches.",
                    )
                )

    interpretation = expectations.interpretation
    if interpretation is not None:
        actual_metric = actual_intent.get("metric")
        actual_dimensions = [_normalize_text(item) for item in actual_intent.get("dimensions") or []]
        actual_filters = list(actual_intent.get("filters") or [])
        actual_date_range = actual_intent.get("date_range") or {}

        if interpretation.metric_any_of:
            matched = _matches_any(actual_metric, interpretation.metric_any_of)
            checks.append(
                CheckOutcome(
                    "understanding",
                    "metric_mismatch" if not matched else "metric_match",
                    matched,
                    1.0 if matched else 0.0,
                    1.0,
                    f"Resolved metric: {actual_metric or '∅'}",
                )
            )

        if interpretation.dimensions_all_of:
            missing = [
                dim for dim in interpretation.dimensions_all_of
                if _normalize_text(dim) not in actual_dimensions
            ]
            passed = not missing
            checks.append(
                CheckOutcome(
                    "understanding",
                    "dimension_missing" if not passed else "dimension_match",
                    passed,
                    1.0 if passed else 0.0,
                    1.0,
                    "Missing dimensions: " + ", ".join(missing) if missing else f"Resolved dimensions: {actual_dimensions}",
                )
            )

        if interpretation.dimensions_any_of:
            matched = any(_normalize_text(dim) in actual_dimensions for dim in interpretation.dimensions_any_of)
            checks.append(
                CheckOutcome(
                    "understanding",
                    "dimension_missing" if not matched else "dimension_any_match",
                    matched,
                    1.0 if matched else 0.0,
                    1.0,
                    f"Resolved dimensions: {actual_dimensions}",
                )
            )

        for expected_filter in interpretation.filters:
            matched = _match_filter(actual_filters, expected_filter)
            checks.append(
                CheckOutcome(
                    "understanding",
                    "filter_missing" if not matched else "filter_match",
                    matched,
                    1.0 if matched else 0.0,
                    1.0,
                    f"Expected filter {expected_filter.model_dump(mode='json')}; actual filters={actual_filters}",
                )
            )

        if interpretation.date_range is not None:
            date_range_match, message = _match_date_range(actual_date_range, interpretation.date_range)
            checks.append(
                CheckOutcome(
                    "understanding",
                    "date_range_mismatch" if not date_range_match else "date_range_match",
                    date_range_match,
                    1.0 if date_range_match else 0.0,
                    1.0,
                    message,
                )
            )

    return checks


def _evaluate_sql(expectations: StepExpectations, actual: dict[str, Any]) -> list[CheckOutcome]:
    sql_expectation = expectations.sql
    if sql_expectation is None:
        return []

    sql = str(actual.get("sql") or "").strip()
    checks: list[CheckOutcome] = []
    if not sql:
        return [CheckOutcome("sql", "sql_missing", False, 0.0, 2.0, "SQL draft is empty.")]

    parsed = None
    parse_error = None
    if sql_expectation.must_parse:
        try:
            parsed = sqlglot.parse_one(sql)
            checks.append(CheckOutcome("sql", "sql_parse_ok", True, 1.0, 1.0, "SQL parsed successfully."))
        except Exception as exc:  # noqa: BLE001
            parse_error = str(exc)
            checks.append(CheckOutcome("sql", "sql_parse_error", False, 0.0, 1.0, f"SQL parse error: {exc}"))

    lowered_sql = sql.lower()
    for needle in sql_expectation.required_substrings:
        passed = needle.lower() in lowered_sql
        checks.append(
            CheckOutcome(
                "sql",
                "sql_required_substring_missing" if not passed else "sql_required_substring_match",
                passed,
                1.0 if passed else 0.0,
                1.0,
                f"Required SQL substring `{needle}` {'found' if passed else 'missing'}.",
            )
        )

    for needle in sql_expectation.forbidden_substrings:
        passed = needle.lower() not in lowered_sql
        checks.append(
            CheckOutcome(
                "sql",
                "sql_forbidden_substring_present" if not passed else "sql_forbidden_substring_ok",
                passed,
                1.0 if passed else 0.0,
                1.0,
                f"Forbidden SQL substring `{needle}` {'not present' if passed else 'present'}.",
            )
        )

    tables, columns = _extract_sql_lineage(parsed, sql) if parse_error is None else (set(), set())
    for table in sql_expectation.required_tables:
        passed = _normalize_text(table) in tables or _normalize_text(table) in lowered_sql
        checks.append(
            CheckOutcome(
                "sql",
                "sql_table_missing" if not passed else "sql_table_match",
                passed,
                1.0 if passed else 0.0,
                1.0,
                f"Required table `{table}` {'found' if passed else 'missing'}; actual tables={sorted(tables)}",
            )
        )

    for table in sql_expectation.forbidden_tables:
        passed = _normalize_text(table) not in tables and _normalize_text(table) not in lowered_sql
        checks.append(
            CheckOutcome(
                "sql",
                "sql_forbidden_table_present" if not passed else "sql_forbidden_table_ok",
                passed,
                1.0 if passed else 0.0,
                1.0,
                f"Forbidden table `{table}` {'not present' if passed else 'present'}; actual tables={sorted(tables)}",
            )
        )

    for column in sql_expectation.required_columns:
        normalized = _normalize_text(column)
        passed = normalized in columns or normalized in lowered_sql
        checks.append(
            CheckOutcome(
                "sql",
                "sql_column_missing" if not passed else "sql_column_match",
                passed,
                1.0 if passed else 0.0,
                1.0,
                f"Required column/alias `{column}` {'found' if passed else 'missing'}; actual columns={sorted(columns)}",
            )
        )
    return checks


def _evaluate_execution_and_chart(expectations: StepExpectations, actual: dict[str, Any]) -> list[CheckOutcome]:
    execution_expectation = expectations.execution
    if execution_expectation is None:
        return []

    checks: list[CheckOutcome] = []
    execution = actual.get("execution") or {}
    if not execution:
        checks.append(CheckOutcome("sql", "execution_missing", False, 0.0, 1.5, "Execution payload is missing."))
        if execution_expectation.chart is not None:
            checks.append(CheckOutcome("chart", "chart_missing", False, 0.0, 1.0, "Chart cannot be evaluated without execution payload."))
        return checks

    execution_error = execution.get("error_message")
    succeeded = not execution_error
    if execution_expectation.should_succeed is not None:
        expected_success = execution_expectation.should_succeed
        passed = succeeded == expected_success
        checks.append(
            CheckOutcome(
                "sql",
                "execution_failed" if not passed else "execution_status_match",
                passed,
                1.0 if passed else 0.0,
                2.0,
                f"Execution {'succeeded' if succeeded else 'failed'}; error={execution_error}",
            )
        )

    if succeeded:
        row_count = int(execution.get("row_count") or 0)
        if execution_expectation.min_row_count is not None:
            passed = row_count >= execution_expectation.min_row_count
            checks.append(
                CheckOutcome(
                    "sql",
                    "execution_row_count_low" if not passed else "execution_row_count_min_ok",
                    passed,
                    1.0 if passed else 0.0,
                    1.0,
                    f"row_count={row_count}, expected at least {execution_expectation.min_row_count}",
                )
            )
        if execution_expectation.max_row_count is not None:
            passed = row_count <= execution_expectation.max_row_count
            checks.append(
                CheckOutcome(
                    "sql",
                    "execution_row_count_high" if not passed else "execution_row_count_max_ok",
                    passed,
                    1.0 if passed else 0.0,
                    1.0,
                    f"row_count={row_count}, expected at most {execution_expectation.max_row_count}",
                )
            )

        actual_columns = {_normalize_text(column.get("name")) for column in execution.get("columns") or [] if column.get("name")}
        for column in execution_expectation.required_columns_all_of:
            passed = any(_matches_column_reference(actual_column, [column]) for actual_column in actual_columns)
            checks.append(
                CheckOutcome(
                    "sql",
                    "execution_required_column_missing" if not passed else "execution_required_column_match",
                    passed,
                    1.0 if passed else 0.0,
                    1.0,
                    f"Expected result column `{column}`; actual columns={sorted(actual_columns)}",
                )
            )

        for group in execution_expectation.required_column_groups:
            passed = any(_matches_column_reference(actual_column, group) for actual_column in actual_columns)
            checks.append(
                CheckOutcome(
                    "sql",
                    "execution_required_column_missing" if not passed else "execution_required_column_group_match",
                    passed,
                    1.0 if passed else 0.0,
                    1.0,
                    f"Expected one of columns {group}; actual columns={sorted(actual_columns)}",
                )
            )

    chart_expectation = execution_expectation.chart
    if chart_expectation is None:
        return checks

    chart = actual.get("chart") or {}
    if not chart:
        checks.append(CheckOutcome("chart", "chart_missing", False, 0.0, 1.0, "Chart recommendation is missing."))
        return checks

    actual_chart_type = chart.get("chart_type") or ("table" if chart.get("recommended_view") == "table" else None)
    if chart_expectation.acceptable_types:
        passed = _matches_any(actual_chart_type, chart_expectation.acceptable_types)
        checks.append(
            CheckOutcome(
                "chart",
                "chart_type_mismatch" if not passed else "chart_type_match",
                passed,
                1.0 if passed else 0.0,
                1.0,
                f"Chart type={actual_chart_type or '∅'}, acceptable={chart_expectation.acceptable_types}",
            )
        )

    if chart_expectation.acceptable_views:
        actual_view = chart.get("recommended_view")
        passed = _matches_any(actual_view, chart_expectation.acceptable_views)
        checks.append(
            CheckOutcome(
                "chart",
                "chart_view_mismatch" if not passed else "chart_view_match",
                passed,
                1.0 if passed else 0.0,
                1.0,
                f"Chart view={actual_view or '∅'}, acceptable={chart_expectation.acceptable_views}",
            )
        )

    if chart_expectation.x_any_of:
        passed = _matches_column_reference(chart.get("x"), chart_expectation.x_any_of)
        checks.append(
            CheckOutcome(
                "chart",
                "chart_x_mismatch" if not passed else "chart_x_match",
                passed,
                1.0 if passed else 0.0,
                1.0,
                f"Chart x={chart.get('x') or '∅'}, acceptable={chart_expectation.x_any_of}",
            )
        )

    if chart_expectation.y_any_of:
        passed = _matches_column_reference(chart.get("y"), chart_expectation.y_any_of)
        checks.append(
            CheckOutcome(
                "chart",
                "chart_y_mismatch" if not passed else "chart_y_match",
                passed,
                1.0 if passed else 0.0,
                1.0,
                f"Chart y={chart.get('y') or '∅'}, acceptable={chart_expectation.y_any_of}",
            )
        )

    if chart_expectation.series_any_of:
        passed = _matches_column_reference(chart.get("series"), chart_expectation.series_any_of)
        checks.append(
            CheckOutcome(
                "chart",
                "chart_series_mismatch" if not passed else "chart_series_match",
                passed,
                1.0 if passed else 0.0,
                1.0,
                f"Chart series={chart.get('series') or '∅'}, acceptable={chart_expectation.series_any_of}",
            )
        )
    return checks


def write_eval_artifacts(result: dict[str, Any], output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_path = output_dir / "results.json"
    summary_path = output_dir / "summary.json"
    failing_steps_path = output_dir / "failing_steps.json"
    repair_brief_path = output_dir / "repair_brief.md"

    summary = result["summary"]
    failing_steps = [
        step
        for case in result["cases"]
        for step in case["steps"]
        if step["scores"]["overall"] < 0.9999
    ]
    failing_steps.sort(key=lambda item: item["scores"]["overall"])

    results_path.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    failing_steps_path.write_text(json.dumps(failing_steps, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    repair_brief_path.write_text(_render_repair_brief(result, failing_steps), encoding="utf-8")

    return {
        "results": str(results_path),
        "summary": str(summary_path),
        "failing_steps": str(failing_steps_path),
        "repair_brief": str(repair_brief_path),
    }


def parse_suite(path: Path) -> EvalSuiteSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EvalSuiteSpec.model_validate(payload)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate /chat text-to-SQL quality end-to-end.")
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path("backend/evals/chat_text_to_sql_suite.json"),
        help="Path to a JSON suite definition.",
    )
    parser.add_argument(
        "--api-base",
        default="http://127.0.0.1:8000/api",
        help="Backend API base URL.",
    )
    parser.add_argument("--database-id", default=None, help="Override database id for all cases.")
    parser.add_argument("--database-name", default=None, help="Override database name for all cases.")
    parser.add_argument("--query-mode", choices=["fast", "thinking"], default=None, help="Override query mode.")
    parser.add_argument("--model-alias", default=None, help="Override chat LLM model alias.")
    parser.add_argument("--with-judge", action="store_true", help="Use configured LLM as an optional QA judge.")
    parser.add_argument("--judge-model-alias", default=None, help="Override judge model alias.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Artifact directory. Default: backend/evals/runs/<timestamp>.")
    parser.add_argument("--fail-under", type=float, default=None, help="Exit non-zero if overall score is below this threshold.")
    args = parser.parse_args(argv)

    suite = parse_suite(args.cases)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or Path("backend/evals/runs") / timestamp

    judge = OptionalLLMJudge(enabled=bool(args.with_judge), model_alias=args.judge_model_alias)
    evaluator = ChatTextToSqlEvaluator(
        args.api_base,
        default_query_mode=args.query_mode or suite.query_mode,
        default_model_alias=args.model_alias or suite.llm_model_alias,
        judge=judge,
    )
    try:
        result = evaluator.run_suite(
            suite,
            database_id_override=args.database_id,
            database_name_override=args.database_name,
            query_mode_override=args.query_mode,
            model_alias_override=args.model_alias,
        )
    finally:
        evaluator.close()

    artifacts = write_eval_artifacts(result, output_dir)
    summary = result["summary"]
    print(f"Suite: {summary['suite_name']}")
    print(f"Cases: {summary['case_count']} | Steps: {summary['step_count']}")
    print(
        "Scores:"
        f" overall={summary['scores']['overall']:.3f}"
        f" understanding={summary['scores']['understanding']:.3f}"
        f" sql={summary['scores']['sql']:.3f}"
        f" chart={summary['scores']['chart']:.3f}"
    )
    if summary["failures_by_code"]:
        print("Top issues:")
        for code, count in list(summary["failures_by_code"].items())[:5]:
            print(f"  - {code}: {count}")
    print("Artifacts:")
    for name, path in artifacts.items():
        print(f"  - {name}: {path}")

    if args.fail_under is not None and summary["scores"]["overall"] < args.fail_under:
        return 2
    return 0


def _structured_payload(send_payload: dict[str, Any]) -> dict[str, Any]:
    return ((send_payload.get("assistant_message") or {}).get("structured_payload") or {})


def _actual_intent(send_payload: dict[str, Any], structured: dict[str, Any]) -> dict[str, Any]:
    intent = ((send_payload.get("session") or {}).get("last_intent_json") or {})
    if intent:
        return intent
    return structured.get("interpretation") or {}


def _extract_sql(send_payload: dict[str, Any]) -> str:
    structured = _structured_payload(send_payload)
    return str(send_payload.get("sql_draft") or structured.get("sql") or "").strip()


def _resolve_clarification_answer(send_payload: dict[str, Any], preferred_reply: str | None = None) -> str | None:
    if preferred_reply and preferred_reply.strip():
        return preferred_reply.strip()
    structured = _structured_payload(send_payload)
    question = str(structured.get("clarification_question") or "").lower()
    if "group" in question or "сгруп" in question:
        return "Hour"
    options = structured.get("clarification_options") or []
    for option in options:
        label = str((option or {}).get("label") or "").strip()
        if label:
            return label
    return None


def _needs_clarification(send_payload: dict[str, Any]) -> bool:
    structured = _structured_payload(send_payload)
    return bool(
        structured.get("state") == "CLARIFYING"
        or structured.get("needs_clarification")
        or structured.get("message_kind") == "clarification"
        or structured.get("clarification_question")
    )


def _contains(value: Any, needle: str) -> bool:
    return _normalize_text(needle) in _normalize_text(value)


def _contains_any(value: Any, needles: list[str]) -> bool:
    normalized = _normalize_text(value)
    return any(_normalize_text(needle) in normalized for needle in needles)


def _matches_any(value: Any, expected_values: list[str]) -> bool:
    normalized = _normalize_text(value)
    if not normalized:
        return False
    for candidate in expected_values:
        normalized_candidate = _normalize_text(candidate)
        if normalized == normalized_candidate or normalized_candidate in normalized or normalized in normalized_candidate:
            return True
    return False


_ALIAS_TOKEN_NORMALIZATIONS = {
    "cnt": "count",
    "count": "count",
    "counts": "count",
    "num": "count",
    "number": "count",
    "total": "total",
    "sum": "total",
    "amount": "revenue",
    "sales": "revenue",
    "revenue": "revenue",
    "payment": "payment",
    "payments": "payment",
    "rental": "rental",
    "rentals": "rental",
    "order": "order",
    "orders": "order",
    "ride": "ride",
    "rides": "ride",
    "trip": "ride",
    "trips": "ride",
    "created": "created",
    "create": "created",
    "completed": "completed",
    "complete": "completed",
    "completion": "completed",
    "done": "completed",
    "accepted": "accepted",
    "accept": "accepted",
    "arrival": "arrival",
    "arrived": "arrival",
    "pickup": "pickup",
    "return": "return",
    "returns": "return",
    "returned": "return",
    "late": "late",
    "rate": "rate",
    "ratio": "rate",
    "share": "rate",
    "conversion": "rate",
    "percent": "rate",
    "pct": "rate",
    "avg": "avg",
    "average": "avg",
    "minutes": "minutes",
    "minute": "minutes",
    "mins": "minutes",
    "min": "minutes",
    "days": "days",
    "day": "day",
    "week": "week",
    "hour": "hour",
    "bucket": "bucket",
}


def _matches_column_reference(value: Any, expected_values: list[str]) -> bool:
    if _matches_any(value, expected_values):
        return True
    return any(_semantic_column_match(value, candidate) for candidate in expected_values)


def _semantic_column_match(actual: Any, expected: Any) -> bool:
    actual_signature = _alias_signature(actual)
    expected_signature = _alias_signature(expected)
    if not actual_signature or not expected_signature:
        return False
    if actual_signature == expected_signature:
        return True
    intersection = actual_signature & expected_signature
    if not intersection:
        return False
    smaller = min(len(actual_signature), len(expected_signature))
    if smaller >= 2 and (actual_signature <= expected_signature or expected_signature <= actual_signature):
        return True
    return (len(intersection) / smaller) >= 0.67


def _alias_signature(value: Any) -> set[str]:
    raw = _normalize_text(value)
    if not raw:
        return set()
    tokens = [token for token in re.split(r"[^a-z0-9]+", raw.replace("_", " ")) if token]
    signature = {_ALIAS_TOKEN_NORMALIZATIONS.get(token, token) for token in tokens}
    if {"not", "completed"} <= signature:
        signature.discard("not")
        signature.add("not_completed")
    if {"accepted", "arrival"} <= signature or {"pickup"} <= signature:
        signature.add("pickup")
    if {"time", "arrival"} <= signature:
        signature.add("pickup")
    if {"avg", "pickup", "minutes"} <= signature:
        signature.add("avg_pickup_duration")
    if {"avg", "ride", "minutes"} <= signature or {"avg", "ride", "duration"} <= signature:
        signature.add("avg_ride_duration")
    if {"hour", "day"} <= signature:
        signature.add("hour")
    return signature


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def _match_filter(actual_filters: list[dict[str, Any]], expected_filter: FilterExpectation) -> bool:
    expected_field = _normalize_text(expected_filter.field)
    expected_operator = _normalize_text(expected_filter.operator) if expected_filter.operator else None
    for actual in actual_filters:
        if _normalize_text(actual.get("field")) != expected_field:
            continue
        if expected_operator and _normalize_text(actual.get("operator")) != expected_operator:
            continue
        actual_value = actual.get("value")
        if expected_filter.value is not None and _normalize_text(actual_value) != _normalize_text(expected_filter.value):
            continue
        if expected_filter.value_any_of and not any(_matches_any(actual_value, [str(item)]) for item in expected_filter.value_any_of):
            continue
        if expected_filter.value_contains and not any(_contains(actual_value, token) for token in expected_filter.value_contains):
            continue
        return True
    return False


def _match_date_range(actual: dict[str, Any], expected: DateRangeExpectation) -> tuple[bool, str]:
    mismatches: list[str] = []
    if expected.kind is not None and _normalize_text(actual.get("kind")) != _normalize_text(expected.kind):
        mismatches.append(f"kind={actual.get('kind')!r} expected {expected.kind!r}")
    if expected.lookback_value is not None and int(actual.get("lookback_value") or -1) != expected.lookback_value:
        mismatches.append(f"lookback_value={actual.get('lookback_value')!r} expected {expected.lookback_value!r}")
    if expected.lookback_unit is not None and _normalize_text(actual.get("lookback_unit")) != _normalize_text(expected.lookback_unit):
        mismatches.append(f"lookback_unit={actual.get('lookback_unit')!r} expected {expected.lookback_unit!r}")
    if expected.start is not None and str(actual.get("start")) != expected.start.isoformat():
        mismatches.append(f"start={actual.get('start')!r} expected {expected.start.isoformat()!r}")
    if expected.end is not None and str(actual.get("end")) != expected.end.isoformat():
        mismatches.append(f"end={actual.get('end')!r} expected {expected.end.isoformat()!r}")
    if mismatches:
        return False, "Date range mismatch: " + "; ".join(mismatches)
    return True, f"Date range matched: {actual}"


def _extract_sql_lineage(parsed: exp.Expression | None, sql: str) -> tuple[set[str], set[str]]:
    if parsed is None:
        lowered = sql.lower()
        return set(), {token for token in lowered.replace(",", " ").split() if "." not in token}
    tables = {_normalize_text(table.name) for table in parsed.find_all(exp.Table) if table.name}
    columns = {_normalize_text(column.name) for column in parsed.find_all(exp.Column) if column.name}
    aliases = {_normalize_text(alias.alias) for alias in parsed.find_all(exp.Alias) if alias.alias}
    return tables, columns | aliases


def _bucket_score_payload(checks: list[CheckOutcome]) -> dict[str, Any]:
    by_bucket: dict[str, list[CheckOutcome]] = defaultdict(list)
    for check in checks:
        by_bucket[check.bucket].append(check)

    scores: dict[str, float] = {}
    applicable_buckets: list[str] = []
    for bucket in ("understanding", "sql", "chart"):
        bucket_checks = by_bucket.get(bucket, [])
        if not bucket_checks:
            scores[bucket] = 1.0
            continue
        applicable_buckets.append(bucket)
        numerator = sum(item.score * item.weight for item in bucket_checks)
        denominator = sum(item.weight for item in bucket_checks) or 1.0
        scores[bucket] = round(numerator / denominator, 4)
    active_scores = [scores[bucket] for bucket in applicable_buckets] or [1.0]
    scores["overall"] = round(sum(active_scores) / len(active_scores), 4)
    return {
        "scores": scores,
        "applicable_buckets": applicable_buckets,
    }


def _aggregate_case_scores(step_results: list[dict[str, Any]]) -> dict[str, float]:
    if not step_results:
        return {"understanding": 1.0, "sql": 1.0, "chart": 1.0, "overall": 1.0}
    return {
        bucket: _average_bucket(step_results, bucket)
        for bucket in ("understanding", "sql", "chart", "overall")
    }


def _build_suite_summary(
    *,
    suite_name: str,
    api_base: str,
    case_results: list[dict[str, Any]],
    started_at: datetime,
    finished_at: datetime,
    judge_used: bool,
) -> dict[str, Any]:
    step_results = [step for case in case_results for step in case["steps"]]
    score_keys = ("understanding", "sql", "chart", "overall")
    scores = {key: _average_bucket(step_results, key) for key in score_keys}
    failures_by_code = Counter(
        check["code"]
        for step in step_results
        for check in step["checks"]
        if not check["passed"]
    )
    return {
        "suite_name": suite_name,
        "api_base": api_base,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "case_count": len(case_results),
        "step_count": len(step_results),
        "scores": scores,
        "judge_used": judge_used,
        "failures_by_code": dict(failures_by_code.most_common()),
    }


def _build_repair_targets(case_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in case_results:
        for step in case["steps"]:
            for check in step["checks"]:
                if check["passed"]:
                    continue
                grouped[check["code"]].append(
                    {
                        "step_ref": step["step_ref"],
                        "prompt": step["user_prompt"],
                        "message": check["message"],
                    }
                )

    targets: list[dict[str, Any]] = []
    for code, failures in grouped.items():
        hint = ISSUE_HINTS.get(code, {})
        targets.append(
            {
                "code": code,
                "count": len(failures),
                "summary": hint.get("summary") or f"Failure group: {code}",
                "files": hint.get("files") or [],
                "examples": failures[:5],
            }
        )
    targets.sort(key=lambda item: (-item["count"], item["code"]))
    return targets


def _average_bucket(step_results: list[dict[str, Any]], bucket: str) -> float:
    if bucket == "overall":
        values = [step["scores"]["overall"] for step in step_results]
    else:
        values = [
            step["scores"][bucket]
            for step in step_results
            if bucket in step.get("applicable_buckets", [])
        ]
    if not values:
        return 1.0
    return round(sum(values) / len(values), 4)


def _render_repair_brief(result: dict[str, Any], failing_steps: list[dict[str, Any]]) -> str:
    summary = result["summary"]
    targets = result["repair_targets"]
    lines = [
        f"# Chat Text-to-SQL Eval: {summary['suite_name']}",
        "",
        f"- API: `{summary['api_base']}`",
        f"- Started: `{summary['started_at']}`",
        f"- Duration: `{summary['duration_seconds']}` sec",
        f"- Scores: overall `{summary['scores']['overall']:.3f}`, understanding `{summary['scores']['understanding']:.3f}`, sql `{summary['scores']['sql']:.3f}`, chart `{summary['scores']['chart']:.3f}`",
        "",
        "## Priority issues",
    ]
    if not targets:
        lines.append("")
        lines.append("No failing checks.")
    else:
        for target in targets[:8]:
            lines.extend(
                [
                    "",
                    f"### {target['code']} ({target['count']})",
                    target["summary"],
                    "",
                    "Suggested files:",
                ]
            )
            if target["files"]:
                lines.extend([f"- `{path}`" for path in target["files"]])
            else:
                lines.append("- No file hints recorded.")
            lines.append("")
            lines.append("Examples:")
            for example in target["examples"]:
                lines.append(f"- `{example['step_ref']}`: {example['message']}")

    lines.extend(["", "## Worst steps"])
    if not failing_steps:
        lines.extend(["", "- No failing steps."])
    else:
        for step in failing_steps[:10]:
            failed_checks = [check for check in step["checks"] if not check["passed"]]
            lines.extend(
                [
                    "",
                    f"### {step['step_ref']} ({step['scores']['overall']:.3f})",
                    f"Prompt: {step['user_prompt']}",
                    f"Actual clarification: {step['actual']['needs_clarification']}",
                    f"Actual SQL: `{str(step['actual'].get('sql') or '')[:240]}`",
                ]
            )
            if step["actual"].get("chart"):
                chart = step["actual"]["chart"]
                lines.append(
                    f"Actual chart: type=`{chart.get('chart_type') or 'table'}` x=`{chart.get('x')}` y=`{chart.get('y')}` series=`{chart.get('series')}`"
                )
            lines.append("Failed checks:")
            for check in failed_checks[:6]:
                lines.append(f"- `{check['code']}`: {check['message']}")
    lines.extend(
        [
            "",
            "## Agent loop",
            "",
            "1. Fix the highest-frequency issue cluster first.",
            "2. Re-run this suite with the same model/mode.",
            "3. Compare `summary.json` and `failing_steps.json` against the previous run.",
            "4. Stop only when the same failure stops reproducing across the targeted cases.",
            "",
        ]
    )
    return "\n".join(lines)


def _extract_json_object(content: str) -> str:
    content = (content or "").strip()
    if content.startswith("{") and content.endswith("}"):
        return content
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM response.")
    return content[start : end + 1]
