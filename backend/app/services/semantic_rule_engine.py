from __future__ import annotations

from collections import defaultdict, deque

from app.schemas.semantic_contract import (
    DimensionCandidate,
    GrainCandidate,
    JoinPathCandidate,
    MetricCandidate,
    SchemaFact,
    SemanticContract,
    TableSemanticProfile,
)


class SemanticRuleEngine:
    MONETARY_HINTS = ("amount", "price", "revenue", "payment", "sales", "fee", "cost", "total")
    QUANTITY_HINTS = ("count", "qty", "quantity", "units", "num", "number")
    DURATION_HINTS = ("duration", "minutes", "hours", "days", "seconds")
    TIME_HINTS = ("created_at", "updated_at", "event_time", "timestamp", "date", "day", "week", "month", "year")
    CATEGORY_HINTS = ("status", "type", "category", "segment", "rating")
    NAME_HINTS = ("name", "title", "label")

    def build_contract(self, *, database_id: str, facts: list[SchemaFact]) -> SemanticContract:
        profiles = [self._profile_table(fact) for fact in facts]
        join_paths = self._build_join_paths(facts)
        return SemanticContract(
            database_id=database_id,
            facts=facts,
            table_profiles=profiles,
            join_paths=join_paths,
        )

    def _profile_table(self, fact: SchemaFact) -> TableSemanticProfile:
        foreign_key_count = len(fact.foreign_keys) + len(fact.inferred_foreign_keys)
        numeric_like = 0
        time_columns: list[str] = []
        measure_candidates: list[MetricCandidate] = []
        dimension_candidates: list[DimensionCandidate] = []
        semantic_tags: list[str] = []

        for column in fact.column_facts:
            lowered = column.column_name.lower()
            if any(hint in lowered for hint in self.TIME_HINTS):
                time_columns.append(column.column_name)
                dimension_candidates.append(
                    DimensionCandidate(
                        column=column.column_name,
                        semantic_role="time",
                        family="time",
                        confidence=0.92,
                        provenance=["rule_engine", "column_name_time_hint"],
                    )
                )
            if any(hint in lowered for hint in self.MONETARY_HINTS):
                numeric_like += 1
                measure_candidates.append(
                    MetricCandidate(
                        metric_name=column.column_name,
                        table=fact.table_name,
                        column=column.column_name,
                        aggregation="sum",
                        confidence=0.93,
                        semantic_family="monetary",
                        forbidden_proxies=["replacement_cost", "rental_rate"] if lowered not in {"amount", "total_amount"} else [],
                        provenance=["rule_engine", "column_name_monetary_hint"],
                    )
                )
                semantic_tags.append("revenue_signal")
            elif any(hint in lowered for hint in self.QUANTITY_HINTS):
                numeric_like += 1
                measure_candidates.append(
                    MetricCandidate(
                        metric_name=column.column_name,
                        table=fact.table_name,
                        column=column.column_name,
                        aggregation="sum" if "count" not in lowered else "count",
                        confidence=0.84,
                        semantic_family="quantity",
                        provenance=["rule_engine", "column_name_quantity_hint"],
                    )
                )
            elif any(hint in lowered for hint in self.DURATION_HINTS):
                numeric_like += 1
                measure_candidates.append(
                    MetricCandidate(
                        metric_name=column.column_name,
                        table=fact.table_name,
                        column=column.column_name,
                        aggregation="avg",
                        confidence=0.82,
                        semantic_family="duration",
                        provenance=["rule_engine", "column_name_duration_hint"],
                    )
                )

            if column.is_foreign_key or lowered.endswith("_id"):
                dimension_candidates.append(
                    DimensionCandidate(
                        column=column.column_name,
                        semantic_role="entity_fk",
                        family="entity",
                        confidence=0.88,
                        provenance=["rule_engine", "foreign_key_shape"],
                    )
                )
            elif any(hint in lowered for hint in self.CATEGORY_HINTS):
                dimension_candidates.append(
                    DimensionCandidate(
                        column=column.column_name,
                        semantic_role="category",
                        family="category",
                        confidence=0.82,
                        provenance=["rule_engine", "category_hint"],
                    )
                )
            elif any(hint in lowered for hint in self.NAME_HINTS):
                dimension_candidates.append(
                    DimensionCandidate(
                        column=column.column_name,
                        semantic_role="label",
                        family="entity",
                        confidence=0.78,
                        provenance=["rule_engine", "label_hint"],
                    )
                )

        table_role = "unknown"
        confidence = 0.55
        if foreign_key_count >= 2 and numeric_like == 0 and len(fact.column_facts) <= 4:
            table_role, confidence = "bridge", 0.92
        elif time_columns and foreign_key_count >= 1 and measure_candidates:
            table_role, confidence = "event", 0.91
        elif foreign_key_count >= 1 and measure_candidates:
            table_role, confidence = "fact", 0.89
        elif len(dimension_candidates) >= 2 and not measure_candidates:
            table_role, confidence = "dimension", 0.84
        elif time_columns and not measure_candidates and foreign_key_count >= 1:
            table_role, confidence = "snapshot", 0.78

        if table_role in {"fact", "event"} and measure_candidates:
            semantic_tags.append("activity_signal")
        if table_role == "dimension":
            semantic_tags.append("reference_data")

        return TableSemanticProfile(
            table=fact.table_name,
            table_role=table_role,
            confidence=confidence,
            grain_candidates=[
                GrainCandidate(
                    grain=fact.primary_key or [column.column_name for column in fact.column_facts if column.is_primary_key],
                    confidence=0.99 if fact.primary_key else 0.52,
                )
            ],
            main_date_column=time_columns[0] if time_columns else None,
            measure_candidates=measure_candidates,
            dimension_candidates=dimension_candidates,
            semantic_tags=sorted(set(semantic_tags)),
            provenance=["rule_engine"],
        )

    def _build_join_paths(self, facts: list[SchemaFact]) -> list[JoinPathCandidate]:
        adjacency: dict[str, list[tuple[str, str, float]]] = defaultdict(list)
        for fact in facts:
            for fk in [*fact.foreign_keys, *fact.inferred_foreign_keys]:
                to_table = str(fk.get("to_table") or "")
                from_column = str(fk.get("from_column") or "")
                to_column = str(fk.get("to_column") or "")
                if not to_table:
                    continue
                expr = f"{fact.table_name}.{from_column} = {to_table}.{to_column}"
                confidence = float(fk.get("confidence") or 0.7)
                adjacency[fact.table_name].append((to_table, expr, confidence))
                adjacency[to_table].append((fact.table_name, expr, confidence))

        paths: list[JoinPathCandidate] = []
        for source in adjacency:
            visited = {source}
            queue = deque([(source, [], [source], 1.0)])
            while queue:
                current, exprs, nodes, conf = queue.popleft()
                for neighbor, expr, edge_conf in adjacency.get(current, []):
                    if neighbor in nodes:
                        continue
                    new_exprs = [*exprs, expr]
                    new_nodes = [*nodes, neighbor]
                    new_conf = min(conf, edge_conf)
                    if len(new_nodes) >= 2:
                        paths.append(
                            JoinPathCandidate(
                                from_table=source,
                                to_table=neighbor,
                                path=new_exprs,
                                path_type="fk_chain",
                                confidence=new_conf,
                                provenance=["rule_engine", "relationship_graph"],
                            )
                        )
                    if neighbor not in visited and len(new_nodes) < 5:
                        visited.add(neighbor)
                        queue.append((neighbor, new_exprs, new_nodes, new_conf))
        deduped: dict[tuple[str, str], JoinPathCandidate] = {}
        for path in paths:
            key = (path.from_table, path.to_table)
            if key not in deduped or deduped[key].confidence < path.confidence:
                deduped[key] = path
        return list(deduped.values())
