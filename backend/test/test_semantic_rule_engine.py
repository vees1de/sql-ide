from __future__ import annotations

from app.schemas.semantic_contract import ColumnFact, SchemaFact
from app.services.semantic_rule_engine import SemanticRuleEngine
from app.services.semantic_validator import SemanticValidator


def test_rule_engine_classifies_transaction_table_and_proxy_metric_warning() -> None:
    engine = SemanticRuleEngine()
    validator = SemanticValidator()
    facts = [
        SchemaFact(
            database_id="db1",
            schema_name="public",
            table_name="payment",
            row_count_estimate=1000,
            primary_key=["payment_id"],
            foreign_keys=[
                {"from_column": "customer_id", "to_table": "customer", "to_column": "customer_id", "confidence": 1.0},
                {"from_column": "staff_id", "to_table": "staff", "to_column": "staff_id", "confidence": 1.0},
            ],
            column_facts=[
                ColumnFact(schema_name="public", table_name="payment", column_name="payment_id", db_type="integer", is_primary_key=True),
                ColumnFact(schema_name="public", table_name="payment", column_name="payment_date", db_type="timestamp"),
                ColumnFact(schema_name="public", table_name="payment", column_name="amount", db_type="numeric"),
                ColumnFact(schema_name="public", table_name="payment", column_name="replacement_cost", db_type="numeric"),
            ],
        )
    ]

    contract = engine.build_contract(database_id="db1", facts=facts)
    contract.validation_issues = validator.validate(contract)

    profile = contract.table_profiles[0]
    assert profile.table_role in {"fact", "event"}
    assert profile.main_date_column == "payment_date"
    assert any(metric.column == "amount" and metric.semantic_family == "monetary" for metric in profile.measure_candidates)
    assert any(issue.code == "proxy_metric_candidate" for issue in contract.validation_issues)


def test_rule_engine_builds_join_paths_from_fk_chain() -> None:
    engine = SemanticRuleEngine()
    facts = [
        SchemaFact(
            database_id="db1",
            schema_name="public",
            table_name="rental",
            foreign_keys=[{"from_column": "inventory_id", "to_table": "inventory", "to_column": "inventory_id", "confidence": 1.0}],
            column_facts=[],
        ),
        SchemaFact(
            database_id="db1",
            schema_name="public",
            table_name="inventory",
            foreign_keys=[{"from_column": "film_id", "to_table": "film", "to_column": "film_id", "confidence": 1.0}],
            column_facts=[],
        ),
        SchemaFact(database_id="db1", schema_name="public", table_name="film", column_facts=[]),
    ]

    contract = engine.build_contract(database_id="db1", facts=facts)

    assert any(path.from_table == "rental" and path.to_table == "film" for path in contract.join_paths)
