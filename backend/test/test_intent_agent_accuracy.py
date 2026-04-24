"""
Intent agent accuracy eval suite.

Focus: classification correctness → SQL quality chain.
A classification is "good" only when it leads the downstream SQL
generator to the right query structure.  Each test therefore checks:
  1. The extracted field (metric / dimension / filter / date_range)
  2. Why it matters for SQL correctness (documented in the test name)
"""

from __future__ import annotations

import pytest

from app.agents.intent import IntentAgent
from app.schemas.query import IntentPayload


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _run(text: str, previous: IntentPayload | None = None) -> IntentPayload:
    return IntentAgent().run(text, previous_intent=previous)


def _make_intent(**kwargs) -> IntentPayload:
    defaults = dict(
        raw_prompt="",
        metric=None,
        dimensions=[],
        filters=[],
        comparison=None,
        date_range=None,
        visualization_preference=None,
        ambiguities=[],
        clarification_question=None,
        confidence=0.5,
        follow_up=False,
    )
    defaults.update(kwargs)
    return IntentPayload(**defaults)


# ===========================================================================
# METRIC EXTRACTION
# ===========================================================================


class TestMetricExtraction:
    """Correct metric → correct aggregation function in SQL."""

    def test_revenue_ru_vyruchka(self):
        assert _run("покажи выручку за месяц").metric == "revenue"

    def test_revenue_en_sales(self):
        assert _run("show total sales last 7 days").metric == "revenue"

    def test_revenue_oborot(self):
        assert _run("оборот по регионам").metric == "revenue"

    def test_order_count_skolko(self):
        assert _run("сколько заказов за неделю").metric == "order_count"

    def test_order_count_top(self):
        # "топ" is mapped to order_count; this drives LIMIT + ORDER BY in SQL
        assert _run("топ 5 городов по заказам").metric == "order_count"

    def test_avg_order_value_sredny_chek(self):
        assert _run("средний чек по каналам").metric == "avg_order_value"

    def test_avg_order_value_aov(self):
        assert _run("what is the AOV by region").metric == "avg_order_value"

    def test_ambiguous_sales_triggers_clarification(self):
        """'Продажи' is ambiguous — must ask, not guess."""
        intent = _run("покажи продажи по месяцам")
        assert intent.metric is None
        assert intent.clarification_question is not None
        assert "продаж" in intent.clarification_question.lower() or "метрик" in intent.clarification_question.lower()

    def test_no_metric_without_context_triggers_clarification(self):
        """Without any metric signal AND no previous intent the agent must ask."""
        intent = _run("по месяцам за последние 3 месяца")
        assert intent.clarification_question is not None

    def test_follow_up_inherits_metric_from_previous_intent(self):
        """Follow-up that adds a filter must not lose the metric from previous turn."""
        prev = _make_intent(metric="revenue", dimensions=["month"])
        intent = _run("теперь только Москва", previous=prev)
        assert intent.metric == "revenue", (
            "Follow-up lost the metric; SQL will miss the aggregation function"
        )


# ===========================================================================
# DIMENSION EXTRACTION
# ===========================================================================


class TestDimensionExtraction:
    """Correct dimension → correct GROUP BY clause in SQL."""

    def test_month_ru(self):
        assert "month" in _run("по месяцам").dimensions

    def test_month_en(self):
        assert "month" in _run("monthly breakdown").dimensions

    def test_week_ru(self):
        assert "week" in _run("по неделям за последний месяц").dimensions

    def test_day_ru(self):
        assert "day" in _run("ежедневная статистика").dimensions

    def test_hour_ru(self):
        assert "hour" in _run("по часам за сегодня").dimensions

    def test_hour_chas(self):
        assert "hour" in _run("разбивку по часам за апрель").dimensions

    def test_city_ru(self):
        assert "city" in _run("по городам").dimensions

    def test_region_ru(self):
        assert "region" in _run("по регионам").dimensions

    def test_channel_ru(self):
        assert "channel" in _run("по каналам привлечения").dimensions

    def test_segment_ru(self):
        assert "segment" in _run("по сегментам клиентов").dimensions

    def test_multiple_dimensions_preserved(self):
        """SQL must have two GROUP BY columns."""
        dims = _run("по городам и по каналам").dimensions
        assert "city" in dims
        assert "channel" in dims

    def test_comparison_auto_adds_month_dimension(self):
        """YoY comparison without explicit dimension should default to month grouping
        so that the SQL has something to group on."""
        intent = _run("выручка по сравнению с прошлым годом")
        assert "month" in intent.dimensions, (
            "YoY without explicit dimension: SQL needs at least month to be meaningful"
        )

    def test_follow_up_inherits_dimension_from_previous(self):
        """Second turn 'только завершённые' must retain the 'hour' grouping."""
        prev = _make_intent(metric="order_count", dimensions=["hour"])
        intent = _run("теперь только завершённые заказы", previous=prev)
        assert "hour" in intent.dimensions, (
            "Follow-up lost the hour dimension; GROUP BY will be wrong"
        )


# ===========================================================================
# FILTER EXTRACTION
# ===========================================================================


class TestFilterExtraction:
    """Correct filter → correct WHERE clause in SQL."""

    def test_city_moscow_ru(self):
        filters = _run("заказы в Москве").filters
        assert any(f.field == "city" and f.value == "Moscow" for f in filters)

    def test_city_spb_ru(self):
        filters = _run("выручка по Санкт-Петербургу").filters
        assert any(f.field == "city" and f.value == "Saint Petersburg" for f in filters)

    def test_city_novosibirsk(self):
        filters = _run("статистика по Новосибирску").filters
        assert any(f.field == "city" and "Novosibirsk" in (f.value or "") for f in filters)

    def test_region_central_ru(self):
        filters = _run("продажи по центральному региону").filters
        assert any(f.field == "region" for f in filters)

    def test_channel_seo(self):
        filters = _run("трафик по SEO-каналу").filters
        assert any(f.field == "channel" for f in filters)

    def test_segment_enterprise(self):
        filters = _run("заказы сегмента Enterprise").filters
        assert any(f.field == "segment" for f in filters)

    def test_no_spurious_filter_on_clean_query(self):
        """Clean query without any entity mention must produce no filters
        to avoid a spurious WHERE that returns 0 rows."""
        intent = _run("выручка по месяцам за последние 3 месяца")
        assert intent.filters == [], f"Spurious filter injected: {intent.filters}"

    def test_follow_up_adds_city_filter_to_existing_intent(self):
        prev = _make_intent(metric="revenue", dimensions=["month"])
        intent = _run("теперь только по Москве", previous=prev)
        assert any(f.field == "city" and f.value == "Moscow" for f in intent.filters), (
            "City filter not added on follow-up; WHERE clause will be missing"
        )


# ===========================================================================
# DATE RANGE EXTRACTION
# ===========================================================================


class TestDateRangeExtraction:
    """Correct date range → correct WHERE on date column in SQL."""

    def test_last_3_months(self):
        dr = _run("за последние 3 месяца").date_range
        assert dr is not None
        assert dr.lookback_value == 3
        assert dr.lookback_unit == "months"

    def test_last_7_days(self):
        dr = _run("за последние 7 дней").date_range
        assert dr is not None
        assert dr.lookback_value == 7
        assert dr.lookback_unit == "days"

    def test_last_2_weeks(self):
        dr = _run("за последние 2 недели").date_range
        assert dr is not None
        assert dr.lookback_value == 2
        assert dr.lookback_unit == "weeks"

    def test_last_month_shorthand(self):
        dr = _run("за прошлый месяц").date_range
        assert dr is not None
        assert dr.lookback_unit == "months"

    def test_last_week_shorthand(self):
        dr = _run("за прошлую неделю").date_range
        assert dr is not None
        assert dr.lookback_unit == "weeks"

    def test_yesterday(self):
        dr = _run("статистика за вчера").date_range
        assert dr is not None
        assert dr.lookback_unit == "days"

    def test_this_year(self):
        dr = _run("выручка в этом году").date_range
        assert dr is not None
        assert dr.kind == "absolute"

    def test_last_year(self):
        dr = _run("итоги прошлого года").date_range
        assert dr is not None
        assert dr.kind == "absolute"

    def test_specific_year(self):
        dr = _run("за 2024 год").date_range
        assert dr is not None
        from datetime import date
        assert dr.start == date(2024, 1, 1)
        assert dr.end == date(2024, 12, 31)

    def test_this_quarter(self):
        dr = _run("выручка в этом квартале").date_range
        assert dr is not None

    def test_last_quarter(self):
        dr = _run("итоги прошлого квартала").date_range
        assert dr is not None

    def test_30_days(self):
        dr = _run("статистика за 30 дней").date_range
        assert dr is not None
        assert dr.lookback_value == 30
        assert dr.lookback_unit == "days"

    def test_no_date_range_when_none_mentioned(self):
        """No date → SQL must not fabricate a date WHERE."""
        dr = _run("покажи топ 5 городов по количеству заказов").date_range
        assert dr is None


# ===========================================================================
# VISUALIZATION PREFERENCE
# ===========================================================================


class TestVisualizationPreference:
    """Correct viz preference → correct chart_type in chart recommendation."""

    def test_pie_chart_ru(self):
        assert _run("покажи распределение заказов").visualization_preference == "pie"

    def test_pie_chart_doля(self):
        assert _run("долю каждого сегмента").visualization_preference == "pie"

    def test_bar_chart_ru(self):
        assert _run("столбчатая диаграмма по городам").visualization_preference == "bar"

    def test_line_chart_dinamika(self):
        assert _run("динамика выручки по месяцам").visualization_preference == "line"

    def test_line_chart_by_months_implicit(self):
        assert _run("выручка по месяцам за квартал").visualization_preference == "line"

    def test_table_explicit(self):
        assert _run("покажи в виде таблицы").visualization_preference == "table"

    def test_no_preference_when_not_requested(self):
        assert _run("выручка в Москве за прошлый месяц").visualization_preference is None


# ===========================================================================
# CONFIDENCE & FOLLOW-UP
# ===========================================================================


class TestConfidenceAndFollowUp:
    """High confidence = agent should go straight to SQL, not ask clarifying questions."""

    def test_high_confidence_with_full_intent(self):
        intent = _run("выручка по месяцам за последние 3 месяца")
        assert intent.confidence >= 0.7, (
            f"Full intent should yield high confidence, got {intent.confidence}"
        )

    def test_low_confidence_on_ambiguous_query(self):
        intent = _run("продажи")
        assert intent.confidence <= 0.5

    def test_follow_up_detected_on_short_refinement(self):
        prev = _make_intent(metric="revenue", dimensions=["month"])
        intent = _run("только по Москве", previous=prev)
        assert intent.follow_up is True

    def test_standalone_full_query_not_flagged_as_follow_up(self):
        intent = _run("покажи выручку по каналам за последние 6 месяцев")
        assert intent.follow_up is False

    def test_ambiguity_lowers_confidence(self):
        with_ambiguity = _run("продажи по регионам")
        without_ambiguity = _run("выручку по регионам")
        assert with_ambiguity.confidence < without_ambiguity.confidence


# ===========================================================================
# COMPARISON EXTRACTION
# ===========================================================================


class TestComparisonExtraction:
    """Correct comparison → SQL needs CTE/subquery for baseline period."""

    def test_yoy_ru(self):
        assert _run("выручка по сравнению с прошлым годом").comparison == "previous_year"

    def test_yoy_en(self):
        assert _run("revenue year over year").comparison == "previous_year"

    def test_yoy_yoy_abbreviation(self):
        assert _run("sales YoY").comparison == "previous_year"

    def test_previous_period(self):
        assert _run("сравни с предыдущим периодом").comparison == "previous_period"

    def test_no_comparison_on_simple_query(self):
        assert _run("выручка по месяцам за последние 3 месяца").comparison is None


# ===========================================================================
# MIXED / COMPLEX QUERIES
# ===========================================================================


class TestComplexQueries:
    """Multi-signal queries that map to complex SQL structures."""

    def test_top_n_by_city_with_date(self):
        """top-5 cities + date range → LIMIT 5 + GROUP BY city + WHERE date."""
        intent = _run("топ 5 городов по количеству заказов за последний месяц")
        assert intent.metric == "order_count"
        assert "city" in intent.dimensions
        assert intent.date_range is not None

    def test_revenue_yoy_with_region_filter(self):
        """YoY + region filter → baseline CTE + WHERE region."""
        intent = _run("выручка по Центральному региону по сравнению с прошлым годом")
        assert intent.metric == "revenue"
        assert intent.comparison == "previous_year"
        assert any(f.field == "region" for f in intent.filters)

    def test_avg_order_value_by_channel_and_city(self):
        intent = _run("средний чек по каналам и городам за этот год")
        assert intent.metric == "avg_order_value"
        assert "channel" in intent.dimensions or "city" in intent.dimensions
        assert intent.date_range is not None

    def test_monthly_revenue_with_yoy_auto_adds_month_dimension(self):
        intent = _run("как изменилась выручка по сравнению с прошлым годом")
        assert "month" in intent.dimensions

    def test_query_with_campaign_filter(self):
        intent = _run("выручка по кампании Spring Sale за последние 2 недели")
        assert any(f.field == "campaign" for f in intent.filters)
        assert intent.date_range is not None
