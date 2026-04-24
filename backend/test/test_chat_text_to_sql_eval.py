from __future__ import annotations

from app.evals.chat_text_to_sql_eval import (
    ChatEvalApiClient,
    DateRangeExpectation,
    ExecutionExpectation,
    InterpretationExpectation,
    FilterExpectation,
    SQLExpectation,
    StepExpectations,
    ChartExpectation,
    ClarificationExpectation,
    _build_repair_targets,
    _matches_column_reference,
    _match_filter,
    _resolve_clarification_answer,
    evaluate_step,
)


def _database() -> dict[str, str]:
    return {"id": "analytics", "name": "Analytics DB", "dialect": "sqlite"}


def test_evaluate_step_scores_perfect_sql_and_chart() -> None:
    expectations = StepExpectations(
        should_clarify=False,
        expected_state="SQL_READY",
        required_actions=["show_run_button", "show_sql"],
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
                "state": "SQL_READY",
                "assistant_message": "SQL готов. Он не будет выполнен автоматически.",
                "actions": [
                    {"type": "show_run_button", "label": "Запустить SQL", "primary": True, "disabled": False, "payload": {"sql_ready": True, "require_user_confirmation": True}},
                    {"type": "show_sql", "label": "Показать SQL", "primary": False, "disabled": False, "payload": {"expanded": True}},
                ],
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
        expected_state="CLARIFYING",
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
                "state": "SQL_READY",
                "assistant_message": "SQL готов.",
                "actions": [
                    {"type": "show_run_button", "label": "Запустить SQL", "primary": True, "disabled": False, "payload": {"sql_ready": True, "require_user_confirmation": True}},
                ],
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


def test_evaluate_step_tracks_sql_ready_actions_without_auto_execute() -> None:
    expectations = StepExpectations(
        should_clarify=False,
        expected_state="SQL_READY",
        required_actions=["show_run_button", "show_sql"],
    )
    send_payload = {
        "session": {"last_intent_json": {"metric": "revenue", "dimensions": ["month"], "filters": []}},
        "assistant_message": {
            "structured_payload": {
                "state": "SQL_READY",
                "assistant_message": "SQL готов. Он не будет выполнен автоматически.",
                "actions": [
                    {"type": "show_run_button", "label": "Запустить SQL", "primary": True, "disabled": False, "payload": {"sql_ready": True, "require_user_confirmation": True}},
                    {"type": "show_sql", "label": "Показать SQL", "primary": False, "disabled": False, "payload": {"expanded": True}},
                ],
                "needs_clarification": False,
                "sql": "SELECT 1 AS total_revenue",
            }
        },
        "sql_draft": "SELECT 1 AS total_revenue",
    }

    result = evaluate_step(
        case_id="sql_ready_without_execute",
        step_index=1,
        database=_database(),
        user_prompt="Подготовь SQL по выручке",
        query_mode="thinking",
        llm_model_alias="gpt120",
        expectations=expectations,
        initial_send_payload=send_payload,
        final_send_payload=send_payload,
        clarification_transcript=[],
        execution_payload=None,
    )

    assert result["actual"]["state"] == "SQL_READY"
    assert result["actual"]["actions"] == ["show_run_button", "show_sql"]
    assert result["actual"]["execution"] is None


def test_evaluate_step_flags_missing_limit_in_top_n_sql() -> None:
    expectations = StepExpectations(
        should_clarify=False,
        expected_state="SQL_READY",
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
                "state": "SQL_READY",
                "assistant_message": "SQL готов. Он не будет выполнен автоматически.",
                "actions": [
                    {"type": "show_run_button", "label": "Запустить SQL", "primary": True, "disabled": False, "payload": {"sql_ready": True, "require_user_confirmation": True}},
                    {"type": "show_sql", "label": "Показать SQL", "primary": False, "disabled": False, "payload": {"expanded": True}},
                ],
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


def test_matches_column_reference_uses_semantic_alias_matching() -> None:
    assert _matches_column_reference("avg_accept_to_arrival_min", ["avg_pickup_minutes", "avg_time_to_arrival"])
    assert _matches_column_reference("share_not_completed", ["non_completion_rate", "not_completed_rate"])
    assert _matches_column_reference("hour_of_day", ["hour", "hour_bucket", "order_hour"])


def test_match_filter_accepts_semantic_value_aliases() -> None:
    assert _match_filter(
        [{"field": "status_order", "operator": "=", "value": "completed"}],
        FilterExpectation(field="status_order", operator="=", value="done"),
    )
    assert _match_filter(
        [{"field": "status_order", "operator": "=", "value": "cancelled"}],
        FilterExpectation(field="status_order", operator="=", value_any_of=["canceled", "cancelled"]),
    )


def test_evaluate_step_accepts_semantically_equivalent_follow_up_filters() -> None:
    expectations = StepExpectations(
        should_clarify=False,
        expected_state="SQL_READY",
        interpretation=InterpretationExpectation(
            dimensions_all_of=["hour"],
            filters=[{"field": "status_order", "operator": "=", "value": "done"}],
        ),
    )
    send_payload = {
        "session": {
            "last_intent_json": {
                "metric": "order_count",
                "dimensions": ["hour"],
                "filters": [
                    {"field": "driverdone_timestamp", "operator": "IS NOT NULL", "value": None},
                    {"field": "order_timestamp", "operator": "=", "value": "2026-04-14"},
                ],
            }
        },
        "assistant_message": {
            "structured_payload": {
                "state": "SQL_READY",
                "assistant_message": "SQL готов. Он не будет выполнен автоматически.",
                "actions": [
                    {"type": "show_run_button", "label": "Запустить SQL", "primary": True, "disabled": False, "payload": {"sql_ready": True, "require_user_confirmation": True}},
                    {"type": "show_sql", "label": "Показать SQL", "primary": False, "disabled": False, "payload": {"expanded": True}},
                ],
                "needs_clarification": False,
                "sql": "SELECT hour, COUNT(*) FROM train WHERE driverdone_timestamp IS NOT NULL GROUP BY hour",
            }
        },
        "sql_draft": "SELECT hour, COUNT(*) FROM train WHERE driverdone_timestamp IS NOT NULL GROUP BY hour",
    }

    result = evaluate_step(
        case_id="follow_up_status_alias",
        step_index=1,
        database=_database(),
        user_prompt="А теперь только завершённые по часам",
        query_mode="thinking",
        llm_model_alias="gpt120",
        expectations=expectations,
        initial_send_payload=send_payload,
        final_send_payload=send_payload,
        clarification_transcript=[],
        execution_payload=None,
    )

    filter_checks = [check for check in result["checks"] if check["code"] in {"filter_match", "filter_missing"}]
    assert filter_checks and all(check["passed"] for check in filter_checks)
    assert result["scores"]["understanding"] == 1.0
