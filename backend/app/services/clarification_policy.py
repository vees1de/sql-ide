from __future__ import annotations

from dataclasses import dataclass

from app.schemas.query import IntentPayload


@dataclass(frozen=True)
class ClarificationPolicyDecision:
    suppress: bool
    cause_code: str | None = None
    detail: str | None = None


class ClarificationPolicy:
    """Deterministic suppression for generic clarification prompts."""

    GENERIC_GROUPING_MARKERS = ("grouped", "grouping", "group by", "сгруп", "группир", "по чему")
    GENERIC_TIME_MARKERS = ("time period", "time range", "timeframe", "period", "врем", "период", "дат")
    GENERIC_METRIC_MARKERS = ("metric", "measure", "метрик", "показател")
    DEFINITION_MARKERS = ("что означает", "что значит", "what does", "what means", "означает")
    OVERLY_CONSERVATIVE_JOIN_MARKERS = (
        "нет прямой связи",
        "нет прямого отношения",
        "no direct link",
        "no direct relationship",
        "cannot directly",
        "нельзя напрямую",
        "нельзя выразить",
        "directly count",
        "не могу напрямую",
        "не могу выразить",
    )

    def should_suppress(
        self,
        *,
        prompt: str,
        intent: IntentPayload,
        question: str | None,
    ) -> ClarificationPolicyDecision:
        if not question:
            return ClarificationPolicyDecision(suppress=False)

        lowered_prompt = prompt.lower()
        lowered_question = question.lower()

        if (
            any(marker in lowered_question for marker in self.GENERIC_GROUPING_MARKERS)
            and self._has_explicit_grouping(prompt=lowered_prompt, intent=intent)
        ):
            return ClarificationPolicyDecision(
                suppress=True,
                cause_code="grouping_already_explicit",
                detail="Prompt already specifies grouping or parsed dimensions.",
            )

        if (
            any(marker in lowered_question for marker in self.GENERIC_TIME_MARKERS)
            and self._has_explicit_time(prompt=lowered_prompt, intent=intent)
        ):
            return ClarificationPolicyDecision(
                suppress=True,
                cause_code="time_already_explicit",
                detail="Prompt already specifies time range or parsed date range.",
            )

        if (
            any(marker in lowered_question for marker in self.GENERIC_METRIC_MARKERS)
            and self._has_explicit_metric(prompt=lowered_prompt, intent=intent)
        ):
            return ClarificationPolicyDecision(
                suppress=True,
                cause_code="metric_already_explicit",
                detail="Prompt already specifies a metric or parsed metric.",
            )

        if (
            any(marker in lowered_question for marker in self.DEFINITION_MARKERS)
            and (
                self._has_explicit_grouping(prompt=lowered_prompt, intent=intent)
                or self._has_explicit_metric(prompt=lowered_prompt, intent=intent)
                or self._has_explicit_time(prompt=lowered_prompt, intent=intent)
            )
        ):
            return ClarificationPolicyDecision(
                suppress=True,
                cause_code="definition_already_explicit",
                detail="Prompt already contains the requested business term or grouping.",
            )

        if (
            any(marker in lowered_question for marker in self.OVERLY_CONSERVATIVE_JOIN_MARKERS)
            and self._has_explicit_analytics_request(prompt=lowered_prompt, intent=intent)
        ):
            return ClarificationPolicyDecision(
                suppress=True,
                cause_code="join_path_overly_conservative",
                detail="Prompt already specifies enough analytics context to continue without a join-path clarification.",
            )

        return ClarificationPolicyDecision(suppress=False)

    def _has_explicit_grouping(self, *, prompt: str, intent: IntentPayload) -> bool:
        if intent.dimensions:
            return True
        grouping_markers = (
            "по час",
            "по дня",
            "по недел",
            "по месяц",
            "по водител",
            "по город",
            "by hour",
            "by day",
            "by week",
            "by month",
            "top-",
            "top ",
        )
        return any(marker in prompt for marker in grouping_markers)

    def _has_explicit_time(self, *, prompt: str, intent: IntentPayload) -> bool:
        if intent.date_range is not None:
            return True
        time_markers = (
            "сегодня",
            "вчера",
            "за ",
            "между ",
            "from ",
            "last ",
            "today",
            "yesterday",
            "апрел",
            "май",
            "июн",
            "202",
        )
        return any(marker in prompt for marker in time_markers)

    def _has_explicit_metric(self, *, prompt: str, intent: IntentPayload) -> bool:
        if intent.metric:
            return True
        metric_markers = (
            "колич",
            "count",
            "sum",
            "avg",
            "average",
            "доля",
            "конверс",
            "выруч",
            "revenue",
            "rate",
        )
        return any(marker in prompt for marker in metric_markers)

    def _has_explicit_analytics_request(self, *, prompt: str, intent: IntentPayload) -> bool:
        return self._has_explicit_metric(prompt=prompt, intent=intent) and (
            self._has_explicit_grouping(prompt=prompt, intent=intent)
            or self._has_explicit_time(prompt=prompt, intent=intent)
        )
