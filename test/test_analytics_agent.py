from __future__ import annotations

from app.schemas.analytics import AnalyticsContext, AnalyticsQueryRequest, DashboardMetadata
from app.schemas.metadata import ColumnMetadata, SchemaMetadataResponse, TableMetadata
from app.schemas.query import IntentPayload, QueryExecutionResult
from app.services.analytics_agent_service import AnalyticsAgentService
from app.services.dashboard_recommendation_service import DashboardRecommendationService


def _schema() -> SchemaMetadataResponse:
    return SchemaMetadataResponse(
        database_id="demo",
        dialect="postgresql",
        tables=[
            TableMetadata(
                name="payment",
                columns=[
                    ColumnMetadata(name="payment_id", type="integer"),
                    ColumnMetadata(name="amount", type="numeric(12,2)"),
                    ColumnMetadata(name="payment_date", type="timestamp without time zone"),
                ],
            )
        ],
        relationships=[],
    )


def test_query_pipeline_returns_sql_chart_and_insight() -> None:
    service = AnalyticsAgentService()
    service._resolve_schema_context = lambda db, context: (_schema(), "postgresql", ["payment"])  # type: ignore[method-assign]
    service._load_dictionary_entries = lambda db: []  # type: ignore[method-assign]
    service._resolve_previous_intent = lambda db, context: None  # type: ignore[method-assign]
    service.execution_service.execute = lambda sql: QueryExecutionResult(  # type: ignore[method-assign]
        sql=sql,
        rows=[
            {"month": "2024-01-01", "total_revenue": 100.0},
            {"month": "2024-02-01", "total_revenue": 150.0},
        ],
        columns=["month", "total_revenue"],
        row_count=2,
        execution_time_ms=12,
    )

    response = service.run_query(
        object(),
        AnalyticsQueryRequest(
            query="Show revenue by month",
            context=AnalyticsContext(database="demo"),
        ),
    )

    assert response.status == "success"
    assert response.sql is not None
    assert "SUM" in response.sql
    assert response.chart is not None
    assert response.chart.chart_type == "line"
    assert response.insight
    assert response.data and response.data[0]["total_revenue"] == 100.0


def test_query_pipeline_requests_clarification_for_ambiguous_query() -> None:
    service = AnalyticsAgentService()
    service._resolve_schema_context = lambda db, context: (_schema(), "postgresql", ["payment"])  # type: ignore[method-assign]
    service._load_dictionary_entries = lambda db: []  # type: ignore[method-assign]
    service._resolve_previous_intent = lambda db, context: None  # type: ignore[method-assign]

    response = service.run_query(
        object(),
        AnalyticsQueryRequest(
            query="Show revenue",
            context=AnalyticsContext(database="demo"),
        ),
    )

    assert response.status == "clarification_required"
    assert response.clarification is not None
    assert response.clarification.questions
    assert len(response.clarification.questions) <= 3


def test_dashboard_recommendation_prefers_matching_dashboard() -> None:
    service = DashboardRecommendationService()
    intent = IntentPayload(raw_prompt="Show revenue by month", metric="revenue", dimensions=["month"], confidence=0.95)
    dashboards = [
        DashboardMetadata(
            id="sales_overview",
            metrics=["revenue"],
            dimensions=["month"],
            analysis_types=["trend"],
            tags=["sales"],
            recency=0.8,
            popularity=0.9,
        ),
        DashboardMetadata(
            id="inventory",
            metrics=["stock"],
            dimensions=["category"],
            analysis_types=["comparison"],
            tags=["ops"],
            recency=0.4,
            popularity=0.2,
        ),
    ]

    recommendation = service.recommend(intent, None, dashboards)

    assert recommendation.best_match is not None
    assert recommendation.best_match.id == "sales_overview"
    assert recommendation.best_match.score > recommendation.alternatives[0].score

