from __future__ import annotations

from app.schemas.semantic_contract import SemanticContract, SemanticValidationIssue


class SemanticValidator:
    def validate(self, contract: SemanticContract) -> list[SemanticValidationIssue]:
        issues: list[SemanticValidationIssue] = []
        fact_tables = {profile.table: profile for profile in contract.table_profiles}
        fact_names = contract.table_names

        for profile in contract.table_profiles:
            if profile.table_role in {"fact", "event"} and not profile.main_date_column:
                issues.append(
                    SemanticValidationIssue(
                        severity="warning",
                        code="missing_main_date",
                        message="Fact/event table has no main date candidate.",
                        table=profile.table,
                    )
                )
            for metric in profile.measure_candidates:
                if metric.column not in {
                    column.column_name
                    for fact in contract.facts if fact.table_name == profile.table
                    for column in fact.column_facts
                }:
                    issues.append(
                        SemanticValidationIssue(
                            severity="error",
                            code="metric_without_backing_column",
                            message="Metric candidate has no physical backing column.",
                            table=profile.table,
                            column=metric.column,
                        )
                    )
                if metric.semantic_family == "monetary" and metric.column in {"replacement_cost", "rental_rate"}:
                    issues.append(
                        SemanticValidationIssue(
                            severity="warning",
                            code="proxy_metric_candidate",
                            message="Proxy monetary column detected; do not prefer it over transaction amounts.",
                            table=profile.table,
                            column=metric.column,
                        )
                    )

        for path in contract.join_paths:
            if path.from_table not in fact_names or path.to_table not in fact_names:
                issues.append(
                    SemanticValidationIssue(
                        severity="error",
                        code="join_path_unknown_table",
                        message="Join path references a table not present in schema facts.",
                        table=path.from_table,
                    )
                )

        for profile in contract.table_profiles:
            if profile.table_role == "dimension" and any(tag == "revenue_signal" for tag in profile.semantic_tags):
                issues.append(
                    SemanticValidationIssue(
                        severity="warning",
                        code="dimension_with_measure_signal",
                        message="Dimension table also looks like a metric source; review role assignment.",
                        table=profile.table,
                    )
                )
        return issues
