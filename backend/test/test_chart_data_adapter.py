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
) -> QuerySemantics:
    is_time_series = x == "month"
    return QuerySemantics(
        intent=intent,
        analysis_mode="trend" if is_time_series else "compare",
        time_role="primary" if is_time_series else "none",
        comparison_goal="composition" if share else "rank" if ranking else "absolute",
        metric=SemanticMetricPayload(name=y, aggregation="sum"),
        comparison=SemanticComparisonPayload(kind="entity_vs_entity", series_column=series) if series else None,
        data_roles=SemanticDataRolesPayload(x=x, y=y, series_key=series, label=x, value=y),
        flags=SemanticFlagsPayload(
            is_time_series=is_time_series,
            is_comparison=bool(series),
            is_ranking=ranking,
            is_share=share,
            explicit_chart_request=False,
        ),
    )


def test_build_single_series_payload_matches_contract() -> None:
    service = ChartDecisionService()
    adapter = ChartDataAdapter()
    execution = _execution(
        ["month", "revenue"],
        [
            {"month": "2026-01", "revenue": 100},
            {"month": "2026-02", "revenue": 120},
        ],
    )

    decision = service.decide(
        _semantics(intent="trend", x="month", y="revenue"),
        execution,
    )
    payload = adapter.build(execution, decision)

    assert payload["kind"] == "single_series"
    assert payload["x"]["field"] == "month"
    assert payload["y"]["field"] == "revenue"
    assert len(payload["x"]["values"]) == len(payload["y"]["values"]) == 2
    assert payload["config"]["valueFormat"] == decision.encoding.value_format


def test_build_multi_series_payload_matches_contract() -> None:
    service = ChartDecisionService()
    adapter = ChartDataAdapter()
    execution = _execution(
        ["month", "city", "revenue"],
        [
            {"month": "2026-01", "city": "Paris", "revenue": 100},
            {"month": "2026-01", "city": "Berlin", "revenue": 120},
            {"month": "2026-02", "city": "Paris", "revenue": 130},
            {"month": "2026-02", "city": "Berlin", "revenue": 125},
        ],
    )

    decision = service.decide(
        _semantics(intent="comparison_over_time", x="month", y="revenue", series="city"),
        execution,
    )
    payload = adapter.build(execution, decision)

    assert payload["kind"] == "multi_series"
    assert payload["seriesField"] == "city"
    assert payload["x"]["field"] == "month"
    assert all(len(item["data"]) == len(payload["x"]["values"]) for item in payload["series"])


def test_build_multi_series_payload_stringifies_numeric_series_names() -> None:
    service = ChartDecisionService()
    adapter = ChartDataAdapter()
    execution = _execution(
        ["month", "city_id", "cancelled_rides_count"],
        [
            {"month": "2026-01", "city_id": 60, "cancelled_rides_count": 10},
            {"month": "2026-01", "city_id": 50, "cancelled_rides_count": 12},
            {"month": "2026-02", "city_id": 60, "cancelled_rides_count": 11},
            {"month": "2026-02", "city_id": 76, "cancelled_rides_count": 7},
        ],
    )

    decision = service.decide(
        _semantics(intent="comparison_over_time", x="month", y="cancelled_rides_count", series="city_id"),
        execution,
    )
    payload = adapter.build(execution, decision)

    assert payload["kind"] == "multi_series"
    assert [item["name"] for item in payload["series"]] == ["60", "50", "76"]
    assert all(isinstance(item["name"], str) for item in payload["series"])
