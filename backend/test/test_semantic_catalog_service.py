from __future__ import annotations

from app.services.semantic_catalog_service import SemanticCatalogService


def test_temporal_dimensions_are_grounded_as_schema_terms() -> None:
    service = SemanticCatalogService()

    resolved = service._resolve_term("day", "dimension", {})

    assert resolved is not None
    assert resolved.resolved is True
    assert resolved.source == "schema"
    assert resolved.match == "day"
