"""Resolve clarification answers (stable option IDs) into IntentPayload patches.

Option IDs follow the convention ``{ambiguity_type}:{value}`` where ``value`` is
either a canonical keyword (``revenue``, ``month``, ``last_30d``) or a
schema-qualified reference like ``orders.amount``.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.agents.intent import IntentAgent
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


_PRESERVE_FIELDS: tuple[str, ...] = ("metric", "dimensions", "filters", "comparison", "visualization_preference")


def merge_with_previous_intent(
    parsed: IntentPayload,
    previous: IntentPayload | None,
) -> IntentPayload:
    """Return ``parsed`` with empty/missing fields filled from ``previous``.

    The fresh parse may drop fields that were already resolved in a prior turn
    (e.g. metric disappears when the user's follow-up message is just a date
    range answer).  Merging before applying clarification answers preserves
    that context without letting stale data override genuinely new values.
    """
    if previous is None:
        return parsed
    update: dict[str, object] = {}
    for field in _PRESERVE_FIELDS:
        new_val = getattr(parsed, field)
        old_val = getattr(previous, field)
        if not new_val and old_val:
            update[field] = old_val
    if parsed.confidence < previous.confidence:
        update["confidence"] = previous.confidence
    if not update:
        return parsed
    return parsed.model_copy(update=update)


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
            date_range = _time_range_from_value(value)
            if date_range is None:
                # LLM-generated option IDs (e.g. "last_two_weeks_data") are not in the
                # static map — fall back to parsing the human-readable option label.
                label_text = (answer.option_label or "").strip()
                if label_text:
                    date_range = IntentAgent()._extract_date_range(label_text)  # noqa: SLF001
            intent.date_range = date_range or intent.date_range
            return intent
        # Unknown kind — fall through to text handling below.

    if text:
        if answer.ambiguity_type == "metric" and not intent.metric:
            intent.metric = text
        elif answer.ambiguity_type == "dimension" and text not in intent.dimensions:
            intent.dimensions = [*intent.dimensions, text]
        elif answer.ambiguity_type == "time_range":
            parsed = IntentAgent()._extract_date_range(text)  # noqa: SLF001
            if parsed is not None:
                intent.date_range = parsed
    return intent


def _canonical_metric(value: str) -> str | None:
    if not value:
        return None
    # "omit_*" options mean the user explicitly chose not to include this metric.
    # Returning None avoids polluting intent.metric with the option ID string.
    if value.startswith("omit") or value == "omit":
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
    if value in {"last_7d", "last_7_days", "last_7days"}:
        return DateRange(kind="relative", start=today - timedelta(days=7), end=today, lookback_value=7, lookback_unit="day")
    if value in {"last_30d", "last_30_days", "last_30days"}:
        return DateRange(kind="relative", start=today - timedelta(days=30), end=today, lookback_value=30, lookback_unit="day")
    if value in {"last_90d", "last_90_days", "last_90days"}:
        return DateRange(kind="relative", start=today - timedelta(days=90), end=today, lookback_value=90, lookback_unit="day")
    if value in {"last_year", "last_1_year", "last_12_months"}:
        return DateRange(kind="relative", start=today - timedelta(days=365), end=today, lookback_value=365, lookback_unit="day")
    if value in {"full_period", "all_time", "all"}:
        return DateRange(kind="all")
    if value == "ytd":
        return DateRange(kind="ytd", start=date(today.year, 1, 1), end=today)
    return None
