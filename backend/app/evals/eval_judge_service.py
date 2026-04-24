from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.core.config import settings

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional runtime dependency
    OpenAI = None


@dataclass(frozen=True)
class EvalJudgeResult:
    score: int
    reason: str
    mode: str = "heuristic"

    def as_dict(self) -> dict[str, Any]:
        return {"score": int(self.score), "reason": self.reason, "mode": self.mode}


class EvalJudgeService:
    def __init__(self, model: str = "gpt-4o-mini") -> None:
        self.model = model
        self._client: OpenAI | None = None

    @property
    def available(self) -> bool:
        return bool(OpenAI is not None and settings.llm_api_base_url and settings.llm_api_key)

    def judge_single_shot(
        self,
        *,
        user_prompt: str,
        generated_sql: str,
        expected_sql_logic: str,
    ) -> EvalJudgeResult:
        if not self.available:
            return self._heuristic_single_shot(user_prompt=user_prompt, generated_sql=generated_sql, expected_sql_logic=expected_sql_logic)

        prompt = (
            "You are an expert SQL evaluator. Your task is to evaluate a generated SQL query against the expected logical requirements.\n\n"
            "[INPUTS]\n"
            f"User Question: {user_prompt}\n"
            f"Generated SQL: {generated_sql}\n"
            f"Expected Logic Checklist: {expected_sql_logic}\n\n"
            "[TASK]\n"
            "1. Does the Generated SQL correctly address the User Question?\n"
            "2. Does the Generated SQL fulfill ALL constraints in the Expected Logic Checklist?\n"
            "3. Check for common pitfalls: Are joins correct? Is division by zero prevented? Is the time frame accurate?\n\n"
            "[OUTPUT FORMAT]\n"
            'Return strictly a JSON object:\n'
            '{\n'
            '  "score": <int between 0 and 1. 1 = Pass, 0 = Fail>,\n'
            '  "reason": "<Short explanation of why it passed or failed, specifying the exact missing logic if failed>"\n'
            "}"
        )
        return self._judge(prompt, fallback=self._heuristic_single_shot(user_prompt=user_prompt, generated_sql=generated_sql, expected_sql_logic=expected_sql_logic))

    def judge_multi_turn(
        self,
        *,
        previous_intent_json: dict[str, Any] | None,
        user_prompt: str,
        generated_intent_json: dict[str, Any] | None,
        expected_intent_json: dict[str, Any],
    ) -> EvalJudgeResult:
        if not self.available:
            return self._heuristic_multi_turn(
                previous_intent_json=previous_intent_json,
                user_prompt=user_prompt,
                generated_intent_json=generated_intent_json,
                expected_intent_json=expected_intent_json,
            )

        prompt = (
            "You are an AI context tracking evaluator. Your task is to determine if an analytical agent correctly updated its memory state based on a follow-up question.\n\n"
            "[INPUTS]\n"
            f"Previous State: {json.dumps(previous_intent_json or {}, ensure_ascii=False)}\n"
            f"User Follow-up: {user_prompt}\n"
            f"Agent's New State: {json.dumps(generated_intent_json or {}, ensure_ascii=False)}\n"
            f"Expected State Constraints: {json.dumps(expected_intent_json, ensure_ascii=False)}\n\n"
            "[TASK]\n"
            "Evaluate if the Agent's New State correctly merged, replaced, or dropped dimensions/metrics/filters as requested by the User Follow-up. Pay special attention to whether old filters that contradict the new prompt were properly removed.\n\n"
            "[OUTPUT FORMAT]\n"
            "Return strictly a JSON object:\n"
            '{\n'
            '  "score": <int 0 or 1>,\n'
            '  "reason": "<Explain what the agent failed to update or carry over>"\n'
            "}"
        )
        return self._judge(prompt, fallback=self._heuristic_multi_turn(
            previous_intent_json=previous_intent_json,
            user_prompt=user_prompt,
            generated_intent_json=generated_intent_json,
            expected_intent_json=expected_intent_json,
        ))

    def judge_edge_case(
        self,
        *,
        user_prompt: str,
        generated_sql: str,
        system_action_log: str,
        expected_behavior: str,
    ) -> EvalJudgeResult:
        if not self.available:
            return self._heuristic_edge_case(
                user_prompt=user_prompt,
                generated_sql=generated_sql,
                system_action_log=system_action_log,
                expected_behavior=expected_behavior,
            )

        prompt = (
            "You are a QA engineer for an analytical text-to-SQL system. \n"
            "The user asked a question designed to return an empty set or trigger an anomaly constraint.\n\n"
            "[INPUTS]\n"
            f"User Question: {user_prompt}\n"
            f"Generated SQL: {generated_sql}\n"
            f"System Action Taken: {system_action_log} (e.g., \"executed normally\", \"triggered repair_sql\")\n"
            f"Expected Behavior: {expected_behavior}\n\n"
            "[TASK]\n"
            "Did the system behave correctly according to the Expected Behavior? \n"
            "Specifically, if the query should legally return 0 rows, check if the system dangerously dropped filters to force a result.\n\n"
            "[OUTPUT FORMAT]\n"
            "Return strictly a JSON object:\n"
            '{\n'
            '  "score": <int 0 or 1>,\n'
            '  "reason": "<Explanation>"\n'
            "}"
        )
        return self._judge(prompt, fallback=self._heuristic_edge_case(
            user_prompt=user_prompt,
            generated_sql=generated_sql,
            system_action_log=system_action_log,
            expected_behavior=expected_behavior,
        ))

    def _client_instance(self) -> OpenAI:
        if self._client is None:
            if OpenAI is None:
                raise RuntimeError("openai package is not installed")
            self._client = OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_api_base_url)
        return self._client

    def _judge(self, prompt: str, fallback: EvalJudgeResult) -> EvalJudgeResult:
        try:
            response = self._client_instance().chat.completions.create(
                model=self.model,
                temperature=0.0,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": "Return exactly one JSON object and no markdown."},
                    {"role": "user", "content": prompt},
                ],
            )
            raw = response.choices[0].message.content or ""
            data = json.loads(_extract_json_object(raw))
            score = 1 if int(data.get("score", 0)) else 0
            reason = str(data.get("reason") or "").strip() or fallback.reason
            return EvalJudgeResult(score=score, reason=reason, mode="llm")
        except Exception:  # noqa: BLE001
            return fallback

    def _heuristic_single_shot(self, *, user_prompt: str, generated_sql: str, expected_sql_logic: str) -> EvalJudgeResult:
        lowered_sql = generated_sql.lower()
        lowered_logic = expected_sql_logic.lower()
        score = 1
        missing: list[str] = []

        if "join" in lowered_logic and "join" not in lowered_sql:
            score = 0
            missing.append("join")
        if "city" in lowered_logic and "city" not in lowered_sql:
            score = 0
            missing.append("city grouping")
        if "tariff" in lowered_logic and "tariff" not in lowered_sql:
            score = 0
            missing.append("tariff grouping")
        if "nullif" in lowered_logic and "nullif" not in lowered_sql:
            score = 0
            missing.append("NULLIF guard")
        if "zero" in lowered_logic and "0 rows" in lowered_logic and "group by" not in lowered_sql:
            score = 0
            missing.append("grouping required for zero-row case")
        if "banned" in lowered_logic and "banned" not in lowered_sql:
            score = 0
            missing.append("banned filter")
        if "completion_rate" in lowered_logic and "completion_rate" not in lowered_sql:
            score = 0
            missing.append("completion_rate")
        if not missing and len(lowered_sql.strip()) < 5:
            score = 0
            missing.append("empty SQL")

        reason = "Heuristic check passed." if score else f"Missing logic: {', '.join(missing) or 'unknown'}."
        return EvalJudgeResult(score=score, reason=reason, mode="heuristic")

    def _heuristic_multi_turn(
        self,
        *,
        previous_intent_json: dict[str, Any] | None,
        user_prompt: str,
        generated_intent_json: dict[str, Any] | None,
        expected_intent_json: dict[str, Any],
    ) -> EvalJudgeResult:
        actual = generated_intent_json or {}
        expected = expected_intent_json or {}
        mismatches: list[str] = []

        if _normalize(actual.get("metric")) != _normalize(expected.get("metric")):
            mismatches.append(f"metric={actual.get('metric')!r}")
        if _normalize_list(actual.get("dimensions")) != _normalize_list(expected.get("dimensions")):
            mismatches.append(f"dimensions={actual.get('dimensions')!r}")
        actual_range = _normalize_date_range(actual.get("date_range"))
        expected_range = _normalize_date_range(expected.get("date_range"))
        for key, expected_value in expected_range.items():
            if actual_range.get(key) != expected_value:
                mismatches.append("date_range")
                break
        if _normalize_filters(actual.get("filters")) != _normalize_filters(expected.get("filters")):
            mismatches.append(f"filters={actual.get('filters')!r}")

        score = 0 if mismatches else 1
        reason = "Heuristic check passed." if score else "Updated state mismatched: " + ", ".join(mismatches)
        return EvalJudgeResult(score=score, reason=reason, mode="heuristic")

    def _heuristic_edge_case(
        self,
        *,
        user_prompt: str,
        generated_sql: str,
        system_action_log: str,
        expected_behavior: str,
    ) -> EvalJudgeResult:
        lowered_sql = generated_sql.lower()
        lowered_log = system_action_log.lower()
        lowered_expected = expected_behavior.lower()

        score = 1
        reasons: list[str] = []
        if "0 rows" in lowered_expected or "empty set" in lowered_expected:
            if "repair_sql" in lowered_log or "dropped" in lowered_log:
                score = 0
                reasons.append("unexpected repair or filter relaxation")
            if not lowered_sql.strip():
                score = 0
                reasons.append("missing SQL")
        if "banned" in lowered_expected and "banned" not in lowered_sql:
            score = 0
            reasons.append("banned filter was removed")
        if "city" in lowered_expected and "city" not in lowered_sql:
            score = 0
            reasons.append("city filter missing")
        reason = "Heuristic check passed." if score else ", ".join(reasons)
        return EvalJudgeResult(score=score, reason=reason, mode="heuristic")


def _normalize(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _normalize_list(value: Any) -> list[str]:
    if not value:
        return []
    if not isinstance(value, list):
        value = [value]
    return sorted(_normalize(item) for item in value if _normalize(item))


def _normalize_date_range(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, Any] = {}
    for key in ("kind", "lookback_value", "lookback_unit", "start", "end"):
        if key in value and value[key] is not None:
            normalized[key] = str(value[key])
    return normalized


def _normalize_filters(value: Any) -> list[tuple[str, str, str]]:
    if not value:
        return []
    result: list[tuple[str, str, str]] = []
    for item in value if isinstance(value, list) else [value]:
        if not isinstance(item, dict):
            continue
        result.append(
            (
                _normalize(item.get("field")),
                _normalize(item.get("operator") or "="),
                _normalize(item.get("value")),
            )
        )
    return sorted(result)


def _extract_json_object(content: str) -> str:
    content = content.strip()
    if content.startswith("{") and content.endswith("}"):
        return content
    match = re.search(r"\{.*\}", content, flags=re.DOTALL)
    if match:
        return match.group(0)
    raise ValueError("No JSON object found in judge response.")
