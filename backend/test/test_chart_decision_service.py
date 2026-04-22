from __future__ import annotations

from app.schemas.query import (
    QueryExecutionResult,
    QuerySemantics,
    SemanticComparisonPayload,
    SemanticDataRolesPayload,
    SemanticFlagsPayload,
    SemanticMetricPayload,
)
from app.services.chart_data_adapter import ChartDataAdapter
from app.services.chart_decision_service import ChartDecisionService


def _execution(columns: list[str], rows: list[dict[str, object]]) -> QueryExecutionResult:
    return QueryExecutionResult(
        sql="select 1",
        rows=rows,
        columns=columns,
        row_count=len(rows),
        execution_time_ms=1,
    )


def _semantics(
    *,
    intent: str,
    x: str,
    y: str,
    series: str | None = None,
    share: bool = False,
    ranking: bool = False,
    hint: str | None = None,
) -> QuerySemantics:
    is_time_series = x == "month"
    return QuerySemantics(
        intent=intent,
        analysis_mode=(
            "delta" if intent == "delta" else
            "rank" if intent == "ranking" else
            "compose" if intent in {"share", "composition_over_time"} else
            "trend" if intent == "trend" else
            "compare"
        ),
        time_role="primary" if is_time_series else "none",
        comparison_goal=(
            "rank" if ranking else
            "composition" if share or intent in {"share", "composition_over_time"} else
            "absolute"
        ),
        metric=SemanticMetricPayload(name=y, aggregation="sum"),
        comparison=SemanticComparisonPayload(kind="entity_vs_entity", series_column=series) if series else None,
        data_roles=SemanticDataRolesPayload(
            x=x,
            y=y,
            series_key=series,
            label=x,
            value=y,
        ),
        flags=SemanticFlagsPayload(
            is_time_series=is_time_series,
            is_comparison=bool(series),
            is_ranking=ranking,
            is_share=share,
            explicit_chart_request=bool(hint),
        ),
        visualization_hint=hint,
    )


def test_comparison_over_time_prefers_grouped_bar_for_few_periods() -> None:
    service = ChartDecisionService()
    execution = _execution(
        ["month", "city", "revenue"],
        [
            {"month": "2026-01", "city": "Paris", "revenue": 100},
            {"month": "2026-01", "city": "Berlin", "revenue": 120},
            {"month": "2026-02", "city": "Paris", "revenue": 130},
            {"month": "2026-02", "city": "Berlin", "revenue": 125},
            {"month": "2026-03", "city": "Paris", "revenue": 160},
            {"month": "2026-03", "city": "Berlin", "revenue": 150},
        ],
    )

    decision = service.decide(
        _semantics(intent="comparison_over_time", x="month", y="revenue", series="city"),
        execution,
    )

    assert decision.chart_type == "bar"
    assert decision.variant == "grouped"
    assert decision.encoding.series_field == "city"
    assert decision.semantic_intent == "comparison_over_time"
    assert decision.query_interpretation is not None
    assert decision.query_interpretation.time_dimension == "month"
    assert decision.query_interpretation.series_dimension == "city"
    assert decision.decision_summary is not None
    assert decision.decision_summary.selected_chart == "grouped_bar"
    assert "INTENT_COMPARISON_OVER_TIME" in decision.reason_codes
    assert "HAS_TIME_AXIS" in decision.reason_codes


def test_comparison_over_time_prefers_multi_line_for_long_timeline() -> None:
    service = ChartDecisionService()
    rows = []
    for month in range(1, 13):
        rows.append({"month": f"2026-{month:02d}", "city": "Paris", "revenue": 100 + month})
        rows.append({"month": f"2026-{month:02d}", "city": "Berlin", "revenue": 120 + month})
    execution = _execution(["month", "city", "revenue"], rows)

    decision = service.decide(
        _semantics(intent="comparison_over_time", x="month", y="revenue", series="city"),
        execution,
    )

    assert decision.chart_type == "line"
    assert decision.variant == "multi_series"
    assert "grouped_bar" in decision.alternatives


def test_share_over_time_uses_stacked_bar_and_not_pie() -> None:
    service = ChartDecisionService()
    execution = _execution(
        ["month", "status", "orders"],
        [
            {"month": "2026-01", "status": "Completed", "orders": 80},
            {"month": "2026-01", "status": "Cancelled", "orders": 20},
            {"month": "2026-02", "status": "Completed", "orders": 70},
            {"month": "2026-02", "status": "Cancelled", "orders": 30},
        ],
    )

    decision = service.decide(
        _semantics(intent="composition_over_time", x="month", y="orders", series="status", share=True),
        execution,
    )

    assert decision.chart_type == "bar"
    assert decision.variant == "stacked"
    assert decision.encoding.normalize == "percent"
    assert decision.chart_type != "pie"


def test_ranking_prefers_horizontal_sorted_bar() -> None:
    service = ChartDecisionService()
    execution = _execution(
        ["city", "total_orders"],
        [
            {"city": "Amsterdam", "total_orders": 120},
            {"city": "Zurich", "total_orders": 95},
            {"city": "Tokyo", "total_orders": 150},
        ],
    )

    decision = service.decide(
        _semantics(intent="ranking", x="city", y="total_orders", ranking=True),
        execution,
    )

    assert decision.chart_type == "bar"
    assert decision.variant == "horizontal_sorted"
    assert decision.encoding.sort == "value_desc"


def test_pie_hint_falls_back_when_category_count_is_too_high() -> None:
    service = ChartDecisionService()
    rows = [{"segment": f"Segment {idx}", "share_value": idx + 1} for idx in range(7)]
    execution = _execution(["segment", "share_value"], rows)

    decision = service.decide(
        _semantics(intent="share", x="segment", y="share_value", share=True, hint="pie"),
        execution,
    )

    assert decision.chart_type == "bar"
    assert "pie_forbidden_above_six_categories" in decision.constraints_applied


def test_multi_line_is_trimmed_to_top_n_plus_other_in_payload() -> None:
    service = ChartDecisionService()
    adapter = ChartDataAdapter()
    rows = []
    series_names = ["A", "B", "C", "D", "E", "F"]
    for month in range(1, 11):
        for index, series_name in enumerate(series_names, start=1):
            rows.append(
                {
                    "month": f"2026-{month:02d}",
                    "city": series_name,
                    "revenue": (len(series_names) - index + 1) * 100 + month,
                }
            )
    execution = _execution(["month", "city", "revenue"], rows)

    decision = service.decide(
        _semantics(intent="comparison_over_time", x="month", y="revenue", series="city"),
        execution,
    )
    payload = adapter.build(execution, decision)

    assert decision.chart_type == "line"
    assert decision.encoding.series_limit == 5
    assert "multi_line_trimmed_to_top_n_plus_other" in decision.constraints_applied
    series_names = [str(item["name"]) for item in payload["series"]]
    assert len(series_names) == 5
    assert "Other" in series_names


def test_category_limit_adds_other_bucket_for_ranking_payload() -> None:
    service = ChartDecisionService()
    adapter = ChartDataAdapter()
    execution = _execution(
        ["city", "orders"],
        [{"city": f"City {idx}", "orders": 100 - idx} for idx in range(12)],
    )

    decision = service.decide(
        _semantics(intent="ranking", x="city", y="orders", ranking=True),
        execution,
    )
    payload = adapter.build(execution, decision)

    assert decision.encoding.category_limit == 10
    assert payload["x"]["values"][-1] == "Other"
    assert len(payload["x"]["values"]) == 10
