from __future__ import annotations

from app.agents.intent import IntentAgent
from app.schemas.query import FilterCondition, IntentPayload


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
