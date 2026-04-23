from __future__ import annotations

from app.schemas.query import QueryExecutionResult
from app.services.ai_chart_suggestion_service import AIChartSuggestionService
from app.services.chart_decision_service import ChartDecisionService
from app.services.chart_spec_service import ChartSpecService
from app.services.llm_service import LLMChartSuggestionPayload


def _execution(columns: list[str], rows: list[dict[str, object]]) -> QueryExecutionResult:
    return QueryExecutionResult(
        sql="select 1",
        rows=rows,
        columns=columns,
        row_count=len(rows),
        execution_time_ms=4,
    )


def test_chart_spec_service_builds_chart_data_from_decision() -> None:
    execution = _execution(
        ["month", "revenue"],
        [
            {"month": "2026-01", "revenue": 100},
            {"month": "2026-02", "revenue": 120},
        ],
    )
    decision = ChartDecisionService().decide(None, execution)

    spec = ChartSpecService().from_decision(
        execution,
        decision,
        title="Автоматическая визуализация",
    )

    assert spec.chart_type == "line"
    assert spec.data is not None
    assert spec.data["kind"] == "single_series"
    assert spec.encoding.x_field == "month"
    assert spec.encoding.y_field == "revenue"


def test_ai_chart_suggestion_applies_valid_override(monkeypatch) -> None:
    execution = _execution(
        ["city", "status", "orders"],
        [
            {"city": "Paris", "status": "Completed", "orders": 12},
            {"city": "Paris", "status": "Cancelled", "orders": 2},
            {"city": "Berlin", "status": "Completed", "orders": 9},
            {"city": "Berlin", "status": "Cancelled", "orders": 1},
        ],
    )
    service = AIChartSuggestionService()

    monkeypatch.setattr(
        service.llm_service,
        "suggest_chart",
        lambda **_kwargs: LLMChartSuggestionPayload(
            chart_type="bar",
            variant="stacked",
            title="Статусы заказов по городам",
            x_field="city",
            y_field="orders",
            series_field="status",
            reason="Есть одна категория и одна разбивка по статусам.",
            explanation="Stacked bar лучше показывает структуру статусов по каждому городу.",
            confidence=0.84,
        ),
    )

    spec = service.suggest(
        goal="best_chart",
        sql="select city, status, orders from t",
        columns=[
            {"name": "city", "type": "object"},
            {"name": "status", "type": "object"},
            {"name": "orders", "type": "int64"},
        ],
        execution=execution,
    )

    assert spec.chart_type == "bar"
    assert spec.variant == "stacked"
    assert spec.encoding.x_field == "city"
    assert spec.encoding.y_field == "orders"
    assert spec.encoding.series_field == "status"
    assert spec.rule_id == "AI_SUGGESTION"


def test_ai_chart_suggestion_falls_back_to_heuristic_when_override_is_invalid(monkeypatch) -> None:
    execution = _execution(
        ["city", "orders"],
        [
            {"city": "Paris", "orders": 12},
            {"city": "Berlin", "orders": 9},
        ],
    )
    service = AIChartSuggestionService()

    monkeypatch.setattr(
        service.llm_service,
        "suggest_chart",
        lambda **_kwargs: LLMChartSuggestionPayload(
            chart_type="pie",
            title="Невалидная подсказка",
            x_field="missing_dimension",
            y_field="orders",
            reason="Попробуем pie.",
            explanation="Но поле для сегментов не существует.",
            confidence=0.61,
        ),
    )

    spec = service.suggest(
        goal="best_chart",
        sql="select city, orders from t",
        columns=[
            {"name": "city", "type": "object"},
            {"name": "orders", "type": "int64"},
        ],
        execution=execution,
    )

    assert spec.chart_type == "bar"
    assert spec.encoding.x_field == "city"
    assert spec.encoding.y_field == "orders"
    assert spec.rule_id == "AI_SUGGESTION"
