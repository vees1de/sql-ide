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
