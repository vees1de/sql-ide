from __future__ import annotations

import re

from app.schemas.semantic_contract import SemanticContract


class SchemaTruthGuard:
    MISSING_MARKERS = (
        "нет таблицы",
        "таблица отсутствует",
        "отсутствует таблица",
        "missing table",
        "table is missing",
        "does not exist",
        "недоступна таблица",
        "нет в текущей схеме",
    )

    def clarification_conflicts_with_schema_truth(
        self,
        *,
        question: str | None,
        contract: SemanticContract | None,
    ) -> bool:
        if not question or contract is None:
            return False
        lowered = question.lower()
        if not any(marker in lowered for marker in self.MISSING_MARKERS):
            return False
        for table_name in contract.table_names:
            if re.search(rf"\b{re.escape(table_name.lower())}\b", lowered):
                return True
        return False
