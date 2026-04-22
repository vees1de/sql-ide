from __future__ import annotations

from app.evals.chat_text_to_sql_eval import (
    ChatEvalApiClient,
    DateRangeExpectation,
    ExecutionExpectation,
    InterpretationExpectation,
    SQLExpectation,
    StepExpectations,
    ChartExpectation,
    ClarificationExpectation,
    _build_repair_targets,
    _resolve_clarification_answer,
    evaluate_step,
)


def _database() -> dict[str, str]:
    return {"id": "demo_analytics", "name": "Demo Analytics DB", "dialect": "sqlite"}


def test_evaluate_step_scores_perfect_sql_and_chart() -> None:
    expectations = StepExpectations(
        should_clarify=False,
        interpretation=InterpretationExpectation(
            metric_any_of=["revenue"],
            dimensions_all_of=["month"],
            date_range=DateRangeExpectation(kind="relative", lookback_value=3, lookback_unit="months"),
        ),
        sql=SQLExpectation(
            required_substrings=["sum(", "group by"],
            required_tables=["orders"],
        ),
        execution=ExecutionExpectation(
            should_succeed=True,
            min_row_count=1,
            required_column_groups=[["month"], ["total_revenue"]],
            chart=ChartExpectation(
                acceptable_types=["line"],
                x_any_of=["month"],
                y_any_of=["total_revenue"],
            ),
        ),
    )

    send_payload = {
        "session": {
            "last_intent_json": {
                "metric": "revenue",
                "dimensions": ["month"],
                "filters": [],
                "date_range": {
                    "kind": "relative",
                    "lookback_value": 3,
                    "lookback_unit": "months",
                },
            }
        },
        "assistant_message": {
            "structured_payload": {
                "message_kind": "answer",
                "needs_clarification": False,
                "sql": "SELECT date(o.order_date, 'start of month') AS month, SUM(o.revenue) AS total_revenue FROM orders o GROUP BY 1",
            }
        },
        "sql_draft": "SELECT date(o.order_date, 'start of month') AS month, SUM(o.revenue) AS total_revenue FROM orders o GROUP BY 1",
    }
    execution_payload = {
        "execution": {
            "error_message": None,
            "row_count": 3,
            "columns": [
                {"name": "month", "type": "date"},
                {"name": "total_revenue", "type": "float"},
            ],
            "chart_recommendation": {
                "recommended_view": "chart",
                "chart_type": "line",
                "x": "month",
                "y": "total_revenue",
                "series": None,
            },
        }
    }

    result = evaluate_step(
        case_id="revenue_by_month",
        step_index=1,
        database=_database(),
        user_prompt="Покажи выручку по месяцам за последние 3 месяца",
        query_mode="thinking",
        llm_model_alias="gpt120",
        expectations=expectations,
        initial_send_payload=send_payload,
        final_send_payload=send_payload,
        clarification_transcript=[],
        execution_payload=execution_payload,
    )

    assert result["scores"]["overall"] == 1.0
    assert result["scores"]["understanding"] == 1.0
    assert result["scores"]["sql"] == 1.0
    assert result["scores"]["chart"] == 1.0
    assert not [check for check in result["checks"] if not check["passed"]]


def test_evaluate_step_flags_missing_clarification() -> None:
    expectations = StepExpectations(
        should_clarify=True,
        clarification=ClarificationExpectation(
            question_should_contain=["выруч", "колич"],
            options_should_include=["выруч", "колич", "средний"],
            min_options=3,
        ),
    )
    send_payload = {
        "session": {"last_intent_json": {"dimensions": ["month"]}},
        "assistant_message": {
            "structured_payload": {
                "message_kind": "answer",
                "needs_clarification": False,
                "clarification_question": None,
            }
        },
        "sql_draft": "SELECT 1",
    }

    result = evaluate_step(
        case_id="clarify_sales_metric",
        step_index=1,
        database=_database(),
        user_prompt="Покажи продажи по месяцам",
        query_mode="thinking",
        llm_model_alias="gpt120",
        expectations=expectations,
        initial_send_payload=send_payload,
        final_send_payload=send_payload,
        clarification_transcript=[],
        execution_payload=None,
    )

    failed_codes = {check["code"] for check in result["checks"] if not check["passed"]}
    assert "clarification_expected" in failed_codes
    assert result["scores"]["understanding"] < 0.5


def test_evaluate_step_flags_missing_limit_in_top_n_sql() -> None:
    expectations = StepExpectations(
        should_clarify=False,
        sql=SQLExpectation(
            required_substrings=["count(", "limit 5"],
            required_tables=["orders", "customers"],
        ),
    )
    send_payload = {
        "session": {
            "last_intent_json": {
                "metric": "order_count",
                "dimensions": ["city"],
                "filters": [],
            }
        },
        "assistant_message": {
            "structured_payload": {
                "message_kind": "answer",
                "needs_clarification": False,
            }
        },
        "sql_draft": (
            "SELECT c.city, COUNT(o.id) AS total_orders "
            "FROM orders o JOIN customers c ON c.id = o.customer_id "
            "GROUP BY c.city ORDER BY total_orders DESC"
        ),
    }

    result = evaluate_step(
        case_id="top_cities_order_count",
        step_index=1,
        database=_database(),
        user_prompt="Покажи топ 5 городов по количеству заказов",
        query_mode="thinking",
        llm_model_alias="gpt120",
        expectations=expectations,
        initial_send_payload=send_payload,
        final_send_payload=send_payload,
        clarification_transcript=[],
        execution_payload=None,
    )

    failed_codes = {check["code"] for check in result["checks"] if not check["passed"]}
    assert "sql_required_substring_missing" in failed_codes
    assert result["scores"]["sql"] < 1.0


def test_build_repair_targets_groups_failures() -> None:
    case_results = [
        {
            "steps": [
                {
                    "step_ref": "clarify_sales_metric#step1",
                    "user_prompt": "Покажи продажи по месяцам",
                    "checks": [
                        {
                            "code": "clarification_expected",
                            "passed": False,
                            "message": "Expected a clarification question.",
                        },
                        {
                            "code": "clarification_options_missing",
                            "passed": False,
                            "message": "Missing clarification option terms.",
                        },
                    ],
                }
            ]
        }
    ]

    targets = _build_repair_targets(case_results)

    assert targets[0]["code"] == "clarification_expected"
    assert "backend/app/services/llm_service.py" in targets[0]["files"]
    assert targets[0]["examples"][0]["step_ref"] == "clarify_sales_metric#step1"


def test_api_client_preserves_api_prefix_in_base_url() -> None:
    client = ChatEvalApiClient("http://127.0.0.1:8000/api")
    try:
        request = client.client.build_request("GET", "chat/databases")
    finally:
        client.close()

    assert str(request.url) == "http://127.0.0.1:8000/api/chat/databases"


def test_resolve_clarification_answer_prefers_explicit_or_hour() -> None:
    payload = {
        "assistant_message": {
            "structured_payload": {
                "clarification_question": "How should the result be grouped?",
                "clarification_options": [
                    {"id": "month", "label": "Month"},
                    {"id": "day", "label": "Day"},
                ],
            }
        }
    }

    assert _resolve_clarification_answer(payload, preferred_reply="driver_id") == "driver_id"
    assert _resolve_clarification_answer(payload) == "Hour"
