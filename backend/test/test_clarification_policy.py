from __future__ import annotations

from app.schemas.query import IntentPayload
from app.services.clarification_policy import ClarificationPolicy


def test_suppresses_generic_grouping_question_when_grouping_is_explicit() -> None:
    policy = ClarificationPolicy()
    intent = IntentPayload(raw_prompt="by hour completed rides", metric="completed_count", dimensions=["hour"], confidence=0.8)

    decision = policy.should_suppress(
        prompt="За 14 апреля 2026 покажи по часам количество завершённых поездок.",
        intent=intent,
        question="How should the result be grouped?",
    )

    assert decision.suppress is True
    assert decision.cause_code == "grouping_already_explicit"


def test_does_not_suppress_specific_question() -> None:
    policy = ClarificationPolicy()
    intent = IntentPayload(raw_prompt="by hour completed rides", metric="completed_count", dimensions=["hour"], confidence=0.8)

    decision = policy.should_suppress(
        prompt="За 14 апреля 2026 покажи по часам количество завершённых поездок.",
        intent=intent,
        question="Учитывать только поездки со статусом done или любые завершённые события водителя?",
    )

    assert decision.suppress is False
    assert decision.cause_code is None


def test_suppresses_overly_conservative_join_path_question_when_prompt_is_specific() -> None:
    policy = ClarificationPolicy()
    intent = IntentPayload(
        raw_prompt="За март 2007 покажи по дням выручку и количество платежей по магазинам.",
        metric="revenue",
        dimensions=["day"],
        confidence=0.9,
    )

    decision = policy.should_suppress(
        prompt="За март 2007 покажи по дням выручку и количество платежей по магазинам.",
        intent=intent,
        question="В схеме нет прямой связи между таблицами inventory и store, поэтому нельзя напрямую посчитать выручку и количество платежей по магазинам. Как вы хотите продолжить?",
    )

    assert decision.suppress is True
    assert decision.cause_code == "join_path_overly_conservative"


def test_suppresses_definition_style_dimension_question_when_prompt_is_explicit() -> None:
    policy = ClarificationPolicy()
    intent = IntentPayload(
        raw_prompt="За март 2007 покажи по дням выручку и количество платежей по магазинам.",
        metric="revenue",
        dimensions=["day"],
        confidence=0.9,
    )

    decision = policy.should_suppress(
        prompt="За март 2007 покажи по дням выручку и количество платежей по магазинам.",
        intent=intent,
        question="Уточните, что означает «day».",
    )

    assert decision.suppress is True
    assert decision.cause_code == "definition_already_explicit"
