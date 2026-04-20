"""Resolve clarification answers (stable option IDs) into IntentPayload patches.

Option IDs follow the convention ``{ambiguity_type}:{value}`` where ``value`` is
either a canonical keyword (``revenue``, ``month``, ``last_30d``) or a
schema-qualified reference like ``orders.amount``.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.schemas.query import ClarificationAnswerRecord, DateRange, IntentPayload

_METRIC_KEYWORDS = {
    "revenue",
    "order_count",
    "avg_order_value",
    "customer_count",
}

_DIMENSION_KEYWORDS = {
    "month",
    "week",
    "day",
    "quarter",
    "year",
    "category",
    "channel",
    "region",
    "product",
}


def apply_answers(intent: IntentPayload, answers: list[ClarificationAnswerRecord]) -> IntentPayload:
    """Return a copy of ``intent`` with clarification answers applied."""
    patched = intent.model_copy(deep=True)
    for answer in answers:
        patched = _apply_single(patched, answer)
    # Clear clarification request once answers are applied so pipeline can proceed.
    if answers:
        patched.clarification_question = None
        patched.ambiguities = []
    return patched


def _apply_single(intent: IntentPayload, answer: ClarificationAnswerRecord) -> IntentPayload:
    option_id = answer.option_id
    text = (answer.text_answer or "").strip()

    if option_id:
        kind, _, value = option_id.partition(":")
        if kind == "metric":
            intent.metric = _canonical_metric(value) or intent.metric
            return intent
        if kind == "dimension":
            dimension = _canonical_dimension(value)
            if dimension and dimension not in intent.dimensions:
                intent.dimensions = [*intent.dimensions, dimension]
            return intent
        if kind == "time_range":
            intent.date_range = _time_range_from_value(value) or intent.date_range
            return intent
        # Unknown kind — fall through to text handling below.

    if text:
        if answer.ambiguity_type == "metric" and not intent.metric:
            intent.metric = text
        elif answer.ambiguity_type == "dimension" and text not in intent.dimensions:
            intent.dimensions = [*intent.dimensions, text]
    return intent


def _canonical_metric(value: str) -> str | None:
    if not value:
        return None
    if value in _METRIC_KEYWORDS:
        return value
    if "." in value:
        # schema-qualified column reference — keep as-is so semantic layer can resolve it
        return value
    return value


def _canonical_dimension(value: str) -> str | None:
    if not value:
        return None
    if value in _DIMENSION_KEYWORDS:
        return value
    if "." in value:
        return value
    return value


def _time_range_from_value(value: str) -> DateRange | None:
    if not value:
        return None
    today = date.today()
    if value == "last_30d":
        return DateRange(kind="relative", start=today - timedelta(days=30), end=today, lookback_value=30, lookback_unit="day")
    if value == "last_90d":
        return DateRange(kind="relative", start=today - timedelta(days=90), end=today, lookback_value=90, lookback_unit="day")
    if value == "ytd":
        return DateRange(kind="ytd", start=date(today.year, 1, 1), end=today)
    if value == "all":
        return DateRange(kind="all")
    return None
