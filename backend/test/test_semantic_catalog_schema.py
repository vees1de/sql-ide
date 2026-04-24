from __future__ import annotations

from app.schemas.semantic_catalog import SemanticColumnEnrichment


def test_semantic_column_enrichment_normalizes_attribute_alias() -> None:
    column = SemanticColumnEnrichment.model_validate(
        {
            "column_name": "order_status",
            "semantic_types": ["attribute", "status"],
            "analytics_roles": [],
            "synonyms": [],
        }
    )

    assert column.semantic_types == ["category", "status"]
