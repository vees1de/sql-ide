from app.agents.intent import IntentAgent
from app.schemas.metadata import ColumnMetadata, SchemaMetadataResponse, TableMetadata
from app.schemas.query import ClarificationAnswerRecord
from app.services.clarification_resolver import apply_answers
from app.services.analytics_agent_service import AnalyticsAgentService


def test_intent_agent_requires_time_range_for_broad_analytics() -> None:
    intent = IntentAgent().run(
        "Хочу увидеть, как у нас проходит заказ от создания до завершения. "
        "Где мы теряем больше всего заказов и сколько времени занимает каждый этап?"
    )

    assert "time_range" in intent.ambiguities
    assert intent.clarification_question == "За какой период показать данные?"


def test_intent_agent_does_not_request_time_range_when_period_is_explicit() -> None:
    intent = IntentAgent().run("За 14 апреля 2026 покажи количество заказов по часам.")

    assert "time_range" not in intent.ambiguities
    assert intent.date_range is not None


def test_time_range_clarification_accepts_free_text_date() -> None:
    intent = IntentAgent().run("Покажи конверсию по часам.")
    resolved = apply_answers(
        intent,
        [
            ClarificationAnswerRecord(
                clarification_id="time_range",
                ambiguity_type="time_range",
                text_answer="За 14 апреля 2026.",
            )
        ],
    )

    assert resolved.date_range is not None
    assert resolved.date_range.start is not None
    assert resolved.date_range.start.isoformat() == "2026-04-14"


def test_metric_clarification_free_text_replaces_unresolved_placeholder() -> None:
    intent = IntentAgent().run("Через какое количество завершенных поездок пассы начинают активнее пользоваться приложением")
    intent.metric = "metric_rides_count"
    intent.ambiguities = ["metric"]
    intent.clarification_question = "Уточните, что означает «metric_rides_count»."

    resolved = apply_answers(
        intent,
        [
            ClarificationAnswerRecord(
                clarification_id="metric",
                ambiguity_type="metric",
                text_answer="Увеличение количества поездок (rides_count)",
            )
        ],
    )

    assert resolved.metric == "Увеличение количества поездок (rides_count)"
    assert resolved.ambiguities == []
    assert resolved.clarification_question is None


def test_metric_clarification_generic_option_uses_free_text_answer() -> None:
    intent = IntentAgent().run("Покажи metric_rides_count")
    intent.metric = "metric_rides_count"

    resolved = apply_answers(
        intent,
        [
            ClarificationAnswerRecord(
                clarification_id="metric",
                ambiguity_type="metric",
                option_id="metric:option",
                option_label="Уточнить вручную",
                text_answer="Увеличение количества поездок (rides_count)",
            )
        ],
    )

    assert resolved.metric == "Увеличение количества поездок (rides_count)"


def test_broad_analytics_prioritizes_time_range_question() -> None:
    intent = IntentAgent().run(
        "Хочу увидеть, как у нас проходит заказ от создания до завершения. "
        "Где мы теряем больше всего заказов и сколько времени занимает каждый этап?"
    )
    schema = SchemaMetadataResponse(
        database_id="drivee",
        dialect="postgresql",
        tables=[
            TableMetadata(
                name="train",
                columns=[
                    ColumnMetadata(
                        name="order_timestamp",
                        type="TIMESTAMP",
                        min_value="2025-01-02 14:34:25",
                        max_value="2026-04-20 13:06:15",
                    )
                ],
            )
        ],
    )

    questions = AnalyticsAgentService()._build_clarification_questions(intent, schema)  # noqa: SLF001

    assert questions[0].id == "time_range"
