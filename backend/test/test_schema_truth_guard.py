from __future__ import annotations

from app.schemas.semantic_contract import SemanticContract, SchemaFact
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
