from __future__ import annotations

from app.schemas.query import ChartSpec, QueryExecutionResult
from app.services.chart_data_adapter import ChartDataAdapter
from app.services.chart_decision_service import ChartDecision


class ChartSpecService:
    def __init__(self) -> None:
        self.chart_data_adapter = ChartDataAdapter()

    def from_decision(
        self,
        execution: QueryExecutionResult,
        decision: ChartDecision,
        *,
        title: str,
    ) -> ChartSpec:
        chart_data = self.chart_data_adapter.build(execution, decision)
        options = {
            "rowCount": execution.row_count,
            "ruleId": decision.rule_id,
            "variant": decision.variant,
            "confidence": decision.confidence,
        }
        return ChartSpec(
            chart_type=decision.chart_type,
            title=title,
            encoding=decision.encoding,
            options=options,
            data=chart_data,
            variant=decision.variant,
            explanation=decision.explanation,
            reason=decision.reason,
            rule_id=decision.rule_id,
            confidence=decision.confidence,
            semantic_intent=decision.semantic_intent,
            analysis_mode=decision.analysis_mode,
            visual_goal=decision.visual_goal,
            time_role=decision.time_role,
            comparison_goal=decision.comparison_goal,
            preferred_mark=decision.preferred_mark,
            alternatives=list(decision.alternatives),
            candidates=list(decision.candidates),
            constraints_applied=list(decision.constraints_applied),
            visual_load=decision.visual_load,
            query_interpretation=decision.query_interpretation,
            decision_summary=decision.decision_summary,
            reason_codes=list(decision.reason_codes),
        )
