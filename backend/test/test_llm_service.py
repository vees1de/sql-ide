from __future__ import annotations

from app.services.llm_service import LLMQueryPlan


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
