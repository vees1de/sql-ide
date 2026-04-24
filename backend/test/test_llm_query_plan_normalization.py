from app.services.llm_service import LLMQueryPlan


def test_llm_query_plan_normalizes_invalid_payload_shapes() -> None:
    plan = LLMQueryPlan.model_validate(
        {
            "state": "CLARIFYING|SQL_READY",
            "assistant_message": None,
            "semantic_parse": {
                "metric": "completion_rate",
                "dimensions": ["hour"],
                "resolved_terms": [
                    {
                        "term": "order_timestamp",
                        "kind": "timestamp",
                        "source": "schemaish",
                    }
                ],
                "unresolved_terms": [
                    {
                        "term": "completion logic",
                        "kind": "metric_definition",
                        "source": "dictionary",
                    }
                ],
            },
            "intent": {
                "raw_prompt": "Покажи completion rate по часам.",
                "metric": "completion_rate",
                "dimensions": ["hour"],
                "clarification_question": None,
                "clarification_options": None,
            },
            "semantics": {
                "analysis_mode": "ranking-ish",
                "time_role": "timeline",
                "comparison_goal": "delta",
                "preferred_mark": "heatmap",
                "comparison": {"kind": "periodic"},
            },
            "sql": "SELECT 1",
            "chart_type": "scatter",
            "visualization_hint": "timeline",
        }
    )

    assert plan.state == "SQL_READY"
    assert plan.intent.clarification_options == []
    assert plan.semantic_parse is not None
    assert plan.semantic_parse.resolved_terms[0].kind == "column"
    assert plan.semantic_parse.resolved_terms[0].source == "unknown"
    assert plan.semantic_parse.unresolved_terms[0].kind == "metric"
    assert plan.semantics is not None
    assert plan.semantics.analysis_mode is None
    assert plan.semantics.time_role is None
    assert plan.semantics.comparison_goal == "delta"
    assert plan.semantics.preferred_mark is None
    assert plan.semantics.comparison is not None
    assert plan.semantics.comparison.kind == "none"
    assert plan.chart_type is None
    assert plan.visualization_hint is None
