from __future__ import annotations

from collections import OrderedDict
from typing import Iterable

from app.schemas.metadata import RelationshipGraphEdge, RelationshipMetadata


def build_relationship_graph(relationships: Iterable[RelationshipMetadata]) -> list[RelationshipGraphEdge]:
    edges: "OrderedDict[tuple[str, str, str], RelationshipGraphEdge]" = OrderedDict()
    for relationship in relationships:
        forward_on = f"{relationship.from_table}.{relationship.from_column} = {relationship.to_table}.{relationship.to_column}"
        reverse_on = f"{relationship.to_table}.{relationship.to_column} = {relationship.from_table}.{relationship.from_column}"

        forward_key = (relationship.from_table, relationship.to_table, forward_on)
        reverse_key = (relationship.to_table, relationship.from_table, reverse_on)

        if forward_key not in edges:
            edges[forward_key] = RelationshipGraphEdge(
                from_table=relationship.from_table,
                to_table=relationship.to_table,
                on=forward_on,
            )
        if reverse_key not in edges:
            edges[reverse_key] = RelationshipGraphEdge(
                from_table=relationship.to_table,
                to_table=relationship.from_table,
                on=reverse_on,
            )

    return list(edges.values())
