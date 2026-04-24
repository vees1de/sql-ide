from __future__ import annotations

from app.agents.clarification import ClarificationAgent
from app.schemas.query import IntentPayload


def test_metric_clarification_returns_five_semantic_options_without_schema() -> None:
    agent = ClarificationAgent()
    intent = IntentPayload(
        raw_prompt="Покажи качество поездок",
        metric=None,
        dimensions=[],
        ambiguities=["metric"],
        clarification_question=None,
        confidence=0.3,
    )

    block = agent.run(intent)

    assert block.question == "Какую метрику имеете в виду?"
    assert 3 <= len(block.options) <= 5
    labels = " ".join(option.label for option in block.options)
    assert "заверш" in labels.lower()
    assert "длитель" in labels.lower()
    assert "дистанц" in labels.lower()
    assert "отмен" in labels.lower()
    assert "прибыт" in labels.lower()
