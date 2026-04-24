from __future__ import annotations

from sqlglot import expressions as exp
from sqlglot import parse_one

from app.schemas.semantic_contract import SemanticContract, SchemaFact
from app.agents.validation import SQLValidationAgent
from app.services.schema_truth_guard import SchemaTruthGuard


def test_guard_detects_false_missing_table_clarification() -> None:
    guard = SchemaTruthGuard()
    contract = SemanticContract(
        database_id="db1",
        facts=[
            SchemaFact(database_id="db1", schema_name="public", table_name="payment"),
            SchemaFact(database_id="db1", schema_name="public", table_name="store"),
        ],
    )

    assert guard.clarification_conflicts_with_schema_truth(
        question="Запрос требует таблицы payment и store, которых нет в текущей схеме. Как поступить?",
        contract=contract,
    ) is True


def test_guard_ignores_non_missing_clarification() -> None:
    guard = SchemaTruthGuard()
    contract = SemanticContract(
        database_id="db1",
        facts=[SchemaFact(database_id="db1", schema_name="public", table_name="payment")],
    )

    assert guard.clarification_conflicts_with_schema_truth(
        question="Как считать выручку: по сумме amount или по количеству платежей?",
        contract=contract,
    ) is False


def test_validation_agent_rewrites_division_without_nullif() -> None:
    agent = SQLValidationAgent()
    validation = agent.run("SELECT revenue / total_orders AS ratio FROM orders", "postgresql")

    assert validation.valid is True
    assert "NULLIF" in validation.sql
    parsed = parse_one(validation.sql, read="postgres")
    div = next(parsed.find_all(exp.Div))
    assert isinstance(div.args.get("expression"), exp.Nullif)
