from __future__ import annotations

import calendar
import re
from datetime import date, timedelta

from app.schemas.query import FilterCondition, IntentPayload


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def subtract_months(anchor: date, months: int) -> date:
    year = anchor.year
    month = anchor.month - months
    while month <= 0:
        month += 12
        year -= 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def shift_year(anchor: date, years: int) -> date:
    target_year = anchor.year + years
    day = min(anchor.day, calendar.monthrange(target_year, anchor.month)[1])
    return date(target_year, anchor.month, day)


def merge_filters(previous_filters: list[FilterCondition], current_filters: list[FilterCondition]) -> list[FilterCondition]:
    merged: dict[str, FilterCondition] = {item.field: item for item in previous_filters}
    for current_filter in current_filters:
        merged[current_filter.field] = current_filter
    return list(merged.values())


def merge_with_context(current: IntentPayload, previous: IntentPayload | None) -> IntentPayload:
    if previous is None:
        return current

    can_inherit = current.follow_up or (
        current.metric is None and (current.dimensions or current.filters or current.comparison)
    )
    if not can_inherit:
        return current

    return IntentPayload(
        raw_prompt=current.raw_prompt,
        metric=current.metric or previous.metric,
        dimensions=current.dimensions or previous.dimensions,
        filters=merge_filters(previous.filters, current.filters),
        comparison=current.comparison or previous.comparison,
        date_range=current.date_range or previous.date_range,
        visualization_preference=current.visualization_preference or previous.visualization_preference,
        ambiguities=current.ambiguities,
        clarification_question=current.clarification_question,
        confidence=current.confidence,
        follow_up=True,
    )


def looks_like_follow_up(prompt: str) -> bool:
    lowered = normalize_text(prompt)
    markers = (
        "теперь",
        "сравни",
        "добавь",
        "оставь",
        "только",
        "убери",
        "а теперь",
        "также",
        "compare",
        "now",
        "only",
        "also",
        "filter",
    )
    return any(marker in lowered for marker in markers) or len(lowered.split()) <= 5


def start_of_current_quarter(anchor: date) -> date:
    quarter = (anchor.month - 1) // 3
    month = quarter * 3 + 1
    return date(anchor.year, month, 1)


def end_of_previous_quarter(anchor: date) -> date:
    current_quarter_start = start_of_current_quarter(anchor)
    return current_quarter_start - timedelta(days=1)


def start_of_previous_quarter(anchor: date) -> date:
    return start_of_current_quarter(end_of_previous_quarter(anchor))
