from __future__ import annotations

from app.agents.intent import IntentAgent
from app.schemas.metadata import ColumnMetadata, SchemaMetadataResponse, TableMetadata
from app.schemas.query import DateRange, FilterCondition, IntentPayload
from app.services.analytics_agent_service import AnalyticsAgentService
from app.services.chat_sql_adapter import ChatSqlAdapter


def test_intent_agent_carries_previous_context_forward_on_follow_up() -> None:
    agent = IntentAgent()
    previous_intent = IntentPayload(
        raw_prompt="Покажи завершённые заказы по дням",
        metric="order_count",
        dimensions=["day"],
        filters=[FilterCondition(field="status_order", operator="=", value="done")],
        confidence=0.9,
    )

    intent = agent.run("А теперь по часам", previous_intent=previous_intent)

    assert intent.follow_up is True
    assert intent.metric == "order_count"
    assert "hour" in intent.dimensions
    assert any(filter_item.field == "status_order" and filter_item.value == "done" for filter_item in intent.filters)


def test_intent_agent_does_not_inject_domain_specific_status_filters() -> None:
    agent = IntentAgent()

    intent = agent.run(
        "А теперь оставь только завершённые заказы и сравни по часам среднее время от принятия до прибытия и среднее время поездки от старта до завершения."
    )

    assert intent.follow_up is True
    assert "hour" in intent.dimensions
    assert not any(filter_item.field == "status_order" for filter_item in intent.filters)


def test_chat_adapter_rejects_llm_follow_up_that_changes_metric_context() -> None:
    adapter = ChatSqlAdapter()
    previous_intent = IntentPayload(
        raw_prompt="Количество уникальных завершенных поездок за 2026 год",
        metric="total_completed_trips",
        filters=[FilterCondition(field="status_order", operator="=", value="done")],
        date_range=DateRange(kind="absolute", start="2026-01-01", end="2026-12-31"),
        confidence=0.9,
    )
    llm_intent = IntentPayload(
        raw_prompt="за 2025 год",
        metric="not_completed_ride_count",
        filters=[FilterCondition(field="driverdone_timestamp", operator="IS NULL", value=None)],
        date_range=DateRange(kind="absolute", start="2025-01-01", end="2025-12-31"),
        follow_up=False,
        confidence=1.0,
    )

    normalized = adapter._normalize_llm_intent_with_context("за 2025 год", llm_intent, previous_intent)

    assert normalized.follow_up is True
    assert normalized.metric == "total_completed_trips"
    assert any(item.field == "status_order" and item.value == "done" for item in normalized.filters)
    assert adapter._llm_plan_conflicts_with_context(
        "за 2025 год",
        llm_intent,
        normalized,
        previous_intent,
        "SELECT COUNT(*) AS not_completed_ride_count FROM train WHERE driverdone_timestamp IS NULL",
    )
    assert adapter._completed_train_sql_uses_timestamp_instead_of_status(
        previous_intent,
        "SELECT COUNT(DISTINCT order_id) FROM train WHERE NOT driverdone_timestamp IS NULL",
    )


def test_drivee_completed_unique_template_uses_status_order_done_for_follow_up() -> None:
    service = AnalyticsAgentService()
    schema = SchemaMetadataResponse(
        database_id="db",
        dialect="postgresql",
        tables=[
            TableMetadata(
                name="train",
                columns=[
                    ColumnMetadata(name=name, type="timestamp" if name.endswith("_timestamp") or name.endswith("_local") else "text")
                    for name in [
                        "order_timestamp",
                        "driveraccept_timestamp",
                        "driverarrived_timestamp",
                        "driverstarttheride_timestamp",
                        "driverdone_timestamp",
                        "clientcancel_timestamp",
                        "drivercancel_timestamp",
                        "cancel_before_accept_local",
                        "city_id",
                        "driver_id",
                        "duration_in_seconds",
                        "price_order_local",
                        "price_tender_local",
                        "status_order",
                        "order_id",
                    ]
                ],
            )
        ],
    )
    previous_intent = IntentPayload(
        raw_prompt="Количество уникальных завершенных поездок за 2026 год",
        metric="total_completed_trips",
        filters=[FilterCondition(field="status_order", operator="=", value="done")],
        date_range=DateRange(kind="absolute", start="2026-01-01", end="2026-12-31"),
    )
    intent = IntentPayload(
        raw_prompt="за 2025 год",
        metric="total_completed_trips",
        filters=[FilterCondition(field="status_order", operator="=", value="done")],
        date_range=DateRange(kind="absolute", start="2025-01-01", end="2025-12-31"),
        follow_up=True,
    )

    sql = service._build_drivee_template_sql(
        intent,
        schema,
        "postgresql",
        prompt_override=service._template_prompt(intent, previous_intent),
    )

    assert sql is not None
    assert "COUNT(DISTINCT order_id)" in sql
    assert "status_order = 'done'" in sql
    assert "driverdone_timestamp IS NOT NULL" not in sql
