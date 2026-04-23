from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.schemas.semantic_contract import ColumnFact, SchemaFact, SemanticArtifact
from app.services.knowledge_service import KnowledgeService


class SchemaFactBuilder:
    def __init__(self) -> None:
        self.knowledge_service = KnowledgeService()

    def build(self, db: Session, database_id: str) -> list[SchemaFact]:
        summary = self.knowledge_service.get_summary(db, database_id)
        facts: list[SchemaFact] = []
        for table_stub in summary.tables:
            table = self.knowledge_service.get_table_by_key(
                db,
                database_id,
                table_stub.schema_name,
                table_stub.table_name,
            )
            if table is None:
                continue
            column_facts = [
                ColumnFact(
                    schema_name=column.schema_name,
                    table_name=column.table_name,
                    column_name=column.column_name,
                    db_type=column.data_type,
                    nullable=bool(column.is_nullable),
                    ordinal_position=int(column.ordinal_position or 0),
                    distinct_count=column.distinct_count,
                    null_ratio=column.null_ratio,
                    top_values=[str(value) for value in (column.sample_values or [])],
                    sample_values=[str(value) for value in (column.sample_values or [])],
                    min_value=column.min_value,
                    max_value=column.max_value,
                    semantic_candidates=self._column_semantic_candidates(column),
                )
                for column in sorted(table.columns, key=lambda item: item.ordinal_position)
            ]
            facts.append(
                SchemaFact(
                    database_id=database_id,
                    schema_name=table.schema_name,
                    table_name=table.table_name,
                    row_count_estimate=table.row_count,
                    primary_key=list(table.primary_key or []),
                    column_facts=column_facts,
                    indexes=[],
                    foreign_keys=[
                        {
                            "from_column": rel.from_column_name,
                            "to_table": rel.to_table_name,
                            "to_column": rel.to_column_name,
                            "confidence": rel.confidence,
                            "source": rel.relation_type,
                        }
                        for rel in getattr(table, "_prefetched_relationships", [])
                        if rel.from_table_name == table.table_name and not rel.is_disabled
                    ],
                    inferred_foreign_keys=[
                        {
                            "from_column": rel.from_column_name,
                            "to_table": rel.to_table_name,
                            "to_column": rel.to_column_name,
                            "confidence": rel.confidence,
                            "source": rel.relation_type,
                        }
                        for rel in getattr(table, "_prefetched_relationships", [])
                        if rel.from_table_name == table.table_name and rel.relation_type != "physical_fk" and not rel.is_disabled
                    ],
                )
            )
        return facts

    def _column_semantic_candidates(self, column: Any) -> list[SemanticArtifact]:
        name = str(column.column_name).lower()
        candidates: list[SemanticArtifact] = []
        for pattern, value in (
            ("_id", "id"),
            ("date", "date"),
            ("time", "timestamp"),
            ("amount", "amount"),
            ("price", "amount"),
            ("revenue", "amount"),
            ("count", "quantity"),
            ("qty", "quantity"),
            ("status", "status"),
            ("category", "category"),
            ("name", "name"),
            ("description", "description"),
            ("code", "code"),
        ):
            if pattern in name:
                candidates.append(
                    SemanticArtifact(
                        value=value,
                        source="schema_scan",
                        confidence=0.8,
                        provenance=[f"column_name_match:{pattern}"],
                    )
                )
        return candidates
