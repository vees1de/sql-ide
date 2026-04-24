from __future__ import annotations

import json
from pathlib import Path


SUITE_PATH = Path(__file__).resolve().parents[1] / "evals" / "drivee_db_tests.json"


def test_drivee_db_suite_is_valid_json() -> None:
    suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))

    assert suite["suite_name"] == "drivee_db_tests"
    assert suite["database_id"] == "30a98b573aef4c069fd14d129e21f82b"
    assert suite["query_mode"] == "thinking"
    assert suite["llm_model_alias"] == "gpt120"
    assert len(suite["cases"]) == 6


def test_drivee_db_suite_covers_core_drivee_failures() -> None:
    suite = json.loads(SUITE_PATH.read_text(encoding="utf-8"))
    case_ids = {case["id"] for case in suite["cases"]}

    assert {
        "hourly_order_count",
        "completion_rate_by_hour",
        "avg_pickup_and_ride_time_by_hour_done_only",
        "top_10_drivers_non_completion_rate",
        "follow_up_add_status_filter",
        "follow_up_add_driver_filter",
    } <= case_ids

    for case in suite["cases"]:
        assert case["steps"], f"case {case['id']} must contain steps"
        for step in case["steps"]:
            assert "user" in step
            assert "expectations" in step
