from __future__ import annotations

from app.services.llm_service import LLMQueryPlan, LLMService


def test_llm_query_plan_treats_explanatory_action_as_drafting() -> None:
    plan = LLMQueryPlan.model_validate(
        {
            "intent": {"raw_prompt": "Что значит column_x?", "confidence": 0.8},
            "assistant_message": "column_x хранит идентификатор заявки.",
            "actions": [
                {
                    "type": "create_sql",
                    "label": "Выгрузить таблицу",
                    "primary": True,
                    "disabled": False,
                    "payload": {"reason": "Prepare a table export from the current chat context."},
                }
            ],
        }
    )

    assert plan.state == "SQL_DRAFTING"
    assert plan.sql is None
    assert plan.actions[0].type == "create_sql"


def test_llm_sql_explanation_falls_back_to_structural_blocks(monkeypatch) -> None:
    service = LLMService()
    monkeypatch.setattr(service, "_configured_for_model", lambda _model: False)

    explanation = service.explain_sql(sql="SELECT id\nFROM users\nWHERE active = true", dialect="postgres")

    assert explanation is not None
    assert explanation.generated_by_ai is False
    assert explanation.blocks
    assert explanation.blocks[0].line_start == 1
    assert explanation.blocks[-1].line_end == 3
