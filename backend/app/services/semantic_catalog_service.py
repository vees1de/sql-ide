from __future__ import annotations

import json
import re
from collections import Counter, defaultdict, deque
from statistics import mean
from typing import Any

from sqlalchemy import MetaData, Table, inspect as sa_inspect, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.dictionary import DictionaryEntryRead
from app.schemas.metadata import ColumnMetadata, RelationshipGraphEdge, RelationshipMetadata, SchemaMetadataResponse, TableMetadata
from app.schemas.semantic_catalog import (
    AnalyticsRole,
    ColumnProfile,
    SemanticCatalog,
    SemanticColumn,
    SemanticJoinPath,
    SemanticRelationship,
    SemanticRetrievalContext,
    SemanticTable,
    SemanticTableEnrichment,
    SemanticType,
    TableRole,
)
from app.db.models import (
    SemanticCatalogColumnModel,
    SemanticCatalogJoinPathModel,
    SemanticCatalogModel,
    SemanticCatalogRelationshipModel,
    SemanticCatalogTableModel,
)
from app.services.database_resolution import resolve_allowed_tables, resolve_dialect, resolve_engine
from app.services.knowledge_service import KnowledgeService
from app.services.llm_service import LLMService
from app.services.relationship_graph import build_relationship_graph


_METRIC_NAME_HINTS = ("amount", "revenue", "sales", "price", "cost", "fee", "profit", "balance", "value")
_COUNT_NAME_HINTS = ("count", "qty", "quantity", "total", "num", "number")
_TIME_NAME_HINTS = ("created_at", "updated_at", "date", "time", "timestamp", "month", "day", "week", "year")
_NAME_HINTS = ("name", "title", "label", "description", "display", "full_name")
_STATUS_HINTS = ("status", "state", "stage", "phase")
_LOCATION_HINTS = ("city", "country", "region", "state", "location", "address", "postal", "zip")
_RATIO_HINTS = ("rate", "ratio", "pct", "percent", "percentage")
_DURATION_HINTS = ("duration", "elapsed", "minutes", "hours", "days", "seconds")


class SemanticCatalogService:
    def __init__(self) -> None:
        self.knowledge_service = KnowledgeService()
        self.llm_service = LLMService()

    def get_catalog(self, db: Session, database_id: str, *, refresh: bool = False) -> SemanticCatalog:
        if not refresh:
            cached = self._load_active_catalog(db, database_id)
            if cached is not None:
                return cached

        catalog = self.build_catalog(db, database_id)
        return self.save_catalog(db, catalog)

    def activate_catalog(self, db: Session, database_id: str, *, refresh: bool = False) -> SemanticCatalog:
        return self.get_catalog(db, database_id, refresh=refresh)

    def save_catalog(self, db: Session, catalog: SemanticCatalog) -> SemanticCatalog:
        source_scan_run_id = self._latest_scan_run_id(db, catalog.database_id)
        self._deactivate_catalogs(db, catalog.database_id)
        catalog_model = SemanticCatalogModel(
            database_id=catalog.database_id,
            dialect=catalog.dialect,
            source_scan_run_id=source_scan_run_id,
            active=True,
            build_mode="llm_enriched" if self.llm_service.configured else "rule_based",
            llm_model=settings.llm_model,
            summary={
                "table_count": len(catalog.tables),
                "relationship_count": len(catalog.relationships),
                "join_path_count": len(catalog.join_paths),
                "graph_edge_count": len(catalog.relationship_graph),
            },
            notes=self._catalog_notes(catalog),
        )
        db.add(catalog_model)
        db.flush()

        table_models: dict[tuple[str, str], SemanticCatalogTableModel] = {}
        for table in catalog.tables:
            table_model = SemanticCatalogTableModel(
                catalog_id=catalog_model.id,
                database_id=catalog.database_id,
                schema_name=table.schema_name,
                table_name=table.table_name,
                label=table.label,
                business_description=table.business_description,
                table_role=table.table_role,
                grain=table.grain,
                main_date_column=table.main_date_column,
                main_entity=table.main_entity,
                synonyms=table.synonyms,
                important_metrics=table.important_metrics,
                important_dimensions=table.important_dimensions,
                row_count_estimate=table.row_count_estimate,
                primary_key=table.primary_key,
                indexes=table.indexes,
                comment=table.comment,
            )
            db.add(table_model)
            db.flush()
            table_models[(table.schema_name, table.table_name)] = table_model

            for column in table.columns:
                db.add(
                    SemanticCatalogColumnModel(
                        catalog_id=catalog_model.id,
                        table_id=table_model.id,
                        database_id=catalog.database_id,
                        schema_name=column.schema_name,
                        table_name=column.table_name,
                        column_name=column.column_name,
                        label=column.label,
                        business_description=column.business_description,
                        semantic_types=list(column.semantic_types),
                        analytics_roles=list(column.analytics_roles),
                        value_type=column.value_type,
                        aggregation=list(column.aggregation),
                        filterable=column.filterable,
                        groupable=column.groupable,
                        sortable=column.sortable,
                        synonyms=list(column.synonyms),
                        example_values=list(column.example_values),
                        data_type=column.data_type,
                        nullable=column.nullable,
                        default_value=column.default_value,
                        max_length=column.max_length,
                        ordinal_position=column.ordinal_position,
                        is_pk=column.is_pk,
                        is_fk=column.is_fk,
                        referenced_table=column.referenced_table,
                        referenced_column=column.referenced_column,
                        comment=column.comment,
                        profile=column.profile.model_dump(mode="json"),
                    )
                )

        for relationship in catalog.relationships:
            db.add(
                SemanticCatalogRelationshipModel(
                    catalog_id=catalog_model.id,
                    database_id=catalog.database_id,
                    from_schema_name=self._relationship_schema(relationship.from_table, catalog.tables),
                    from_table_name=relationship.from_table,
                    from_column_name=relationship.from_column,
                    to_schema_name=self._relationship_schema(relationship.to_table, catalog.tables),
                    to_table_name=relationship.to_table,
                    to_column_name=relationship.to_column,
                    relationship_type=relationship.relationship_type,
                    join_type=relationship.join_type,
                    business_meaning=relationship.business_meaning,
                    join_priority=relationship.join_priority,
                    confidence=relationship.confidence,
                    path_id=relationship.path_id,
                )
            )

        for path in catalog.join_paths:
            db.add(
                SemanticCatalogJoinPathModel(
                    catalog_id=catalog_model.id,
                    database_id=catalog.database_id,
                    path_id=path.path_id,
                    from_table=path.from_table,
                    to_table=path.to_table,
                    joins=path.joins,
                    business_use_case=path.business_use_case,
                    tables=path.tables,
                )
            )

        db.commit()
        db.refresh(catalog_model)
        return self._catalog_from_record(db, catalog_model.id)

    def load_catalog(self, db: Session, database_id: str) -> SemanticCatalog | None:
        return self._load_active_catalog(db, database_id)

    def build_catalog(self, db: Session, database_id: str) -> SemanticCatalog:
        target = self._resolve_target(db, database_id)
        inspector = sa_inspect(target["engine"])
        schema_map = self._load_knowledge_tables(db, database_id)

        tables: list[SemanticTable] = []
        relationships: list[SemanticRelationship] = []

        for table_key in target["table_keys"]:
            schema_name, table_name = table_key
            physical = schema_map.get(table_key)
            table = self._build_table(
                inspector=inspector,
                engine=target["engine"],
                schema_name=schema_name,
                table_name=table_name,
                physical=physical,
            )
            tables.append(table)
            relationships.extend(table.relationships)

        join_paths = self._build_join_paths(tables, relationships)
        relationship_graph = build_relationship_graph(relationships)
        for table in tables:
            table.join_paths = [path for path in join_paths if path.from_table == table.table_name or path.to_table == table.table_name]
        tables = self._apply_llm_enrichment(tables, relationship_graph)

        return SemanticCatalog(
            database_id=database_id,
            dialect=target["dialect"],
            tables=tables,
            relationships=relationships,
            join_paths=join_paths,
            relationship_graph=relationship_graph,
        )

    def delete_database_catalog(self, db: Session, database_id: str) -> None:
        db.query(SemanticCatalogJoinPathModel).filter(SemanticCatalogJoinPathModel.database_id == database_id).delete(
            synchronize_session=False
        )
        db.query(SemanticCatalogRelationshipModel).filter(
            SemanticCatalogRelationshipModel.database_id == database_id
        ).delete(synchronize_session=False)
        db.query(SemanticCatalogColumnModel).filter(SemanticCatalogColumnModel.database_id == database_id).delete(
            synchronize_session=False
        )
        db.query(SemanticCatalogTableModel).filter(SemanticCatalogTableModel.database_id == database_id).delete(
            synchronize_session=False
        )
        db.query(SemanticCatalogModel).filter(SemanticCatalogModel.database_id == database_id).delete(
            synchronize_session=False
        )

    def build_retrieval_context(
        self,
        db: Session,
        database_id: str,
        intent_text: str,
        dictionary_entries: list[DictionaryEntryRead] | None = None,
    ) -> SemanticRetrievalContext:
        catalog = self.get_catalog(db, database_id)
        dictionary_entries = dictionary_entries or []
        intent_tokens = self._tokenize(intent_text)

        scored_tables = sorted(
            catalog.tables,
            key=lambda table: self._score_table(table, intent_tokens),
            reverse=True,
        )
        selected_tables = self._expand_related_tables(scored_tables[:4], catalog.tables, catalog.relationships, limit=5)
        selected_table_names = {table.table_name for table in selected_tables}
        selected_columns = {
            f"{column.table_name}.{column.column_name}"
            for table in selected_tables
            for column in table.columns
            if self._score_column(column, intent_tokens) > 0
            or column.analytics_roles
            or column.semantic_types
            or column.is_pk
            or column.is_fk
        }
        selected_join_paths = [
            path
            for path in catalog.join_paths
            if path.from_table in selected_table_names or path.to_table in selected_table_names
        ]
        selected_relationships = [
            rel
            for rel in catalog.relationships
            if rel.from_table in selected_table_names or rel.to_table in selected_table_names
        ]
        selected_graph = build_relationship_graph(selected_relationships)
        schema = self._catalog_to_schema(
            catalog.database_id,
            catalog.dialect,
            selected_tables,
            selected_join_paths,
            selected_graph,
        )
        catalog_entries = self._catalog_to_dictionary_entries(selected_tables, selected_join_paths)
        dictionary_entries = self._merge_dictionary_entries(dictionary_entries, catalog_entries, selected_columns)

        return SemanticRetrievalContext(
            catalog=SemanticCatalog(
                database_id=catalog.database_id,
                dialect=catalog.dialect,
                tables=selected_tables,
                relationships=selected_relationships,
                join_paths=selected_join_paths,
                relationship_graph=selected_graph,
            ),
            schema=schema,
            dictionary_entries=[entry.model_dump(mode="json") for entry in dictionary_entries],
            table_names=sorted(selected_table_names),
            notes=self._build_notes(selected_tables, selected_join_paths),
        )

    def build_schema_context(
        self,
        db: Session,
        database_id: str,
        intent_text: str = "",
        dictionary_entries: list[DictionaryEntryRead] | None = None,
    ) -> SchemaMetadataResponse:
        return SchemaMetadataResponse.model_validate(
            self.build_retrieval_context(db, database_id, intent_text, dictionary_entries).schema
        )

    def _load_active_catalog(self, db: Session, database_id: str) -> SemanticCatalog | None:
        catalog_model = (
            db.query(SemanticCatalogModel)
            .filter(
                SemanticCatalogModel.database_id == database_id,
                SemanticCatalogModel.active.is_(True),
            )
            .order_by(SemanticCatalogModel.created_at.desc())
            .first()
        )
        if catalog_model is None:
            return None
        return self._catalog_from_record(db, catalog_model.id)

    def _catalog_from_record(self, db: Session, catalog_id: str) -> SemanticCatalog:
        catalog_model = (
            db.query(SemanticCatalogModel)
            .filter(SemanticCatalogModel.id == catalog_id)
            .first()
        )
        if catalog_model is None:
            raise ValueError("Semantic catalog not found.")

        table_models = (
            db.query(SemanticCatalogTableModel)
            .filter(SemanticCatalogTableModel.catalog_id == catalog_id)
            .order_by(SemanticCatalogTableModel.schema_name.asc(), SemanticCatalogTableModel.table_name.asc())
            .all()
        )
        column_models = (
            db.query(SemanticCatalogColumnModel)
            .filter(SemanticCatalogColumnModel.catalog_id == catalog_id)
            .order_by(
                SemanticCatalogColumnModel.schema_name.asc(),
                SemanticCatalogColumnModel.table_name.asc(),
                SemanticCatalogColumnModel.ordinal_position.asc(),
            )
            .all()
        )
        relationship_models = (
            db.query(SemanticCatalogRelationshipModel)
            .filter(SemanticCatalogRelationshipModel.catalog_id == catalog_id)
            .order_by(
                SemanticCatalogRelationshipModel.from_table_name.asc(),
                SemanticCatalogRelationshipModel.from_column_name.asc(),
            )
            .all()
        )
        join_path_models = (
            db.query(SemanticCatalogJoinPathModel)
            .filter(SemanticCatalogJoinPathModel.catalog_id == catalog_id)
            .order_by(SemanticCatalogJoinPathModel.path_id.asc())
            .all()
        )

        table_map: dict[tuple[str, str], SemanticTable] = {}
        tables: list[SemanticTable] = []
        for table_model in table_models:
            table = SemanticTable(
                schema_name=table_model.schema_name,
                table_name=table_model.table_name,
                label=table_model.label,
                business_description=table_model.business_description,
                table_role=table_model.table_role,  # type: ignore[arg-type]
                grain=table_model.grain,
                main_date_column=table_model.main_date_column,
                main_entity=table_model.main_entity,
                synonyms=list(table_model.synonyms or []),
                important_metrics=list(table_model.important_metrics or []),
                important_dimensions=list(table_model.important_dimensions or []),
                row_count_estimate=table_model.row_count_estimate,
                primary_key=list(table_model.primary_key or []),
                indexes=list(table_model.indexes or []),
                comment=table_model.comment,
                columns=[],
                relationships=[],
                join_paths=[],
            )
            table_map[(table.schema_name, table.table_name)] = table
            tables.append(table)

        relationships: list[SemanticRelationship] = []
        for relationship_model in relationship_models:
            relationship = SemanticRelationship(
                from_table=relationship_model.from_table_name,
                from_column=relationship_model.from_column_name,
                to_table=relationship_model.to_table_name,
                to_column=relationship_model.to_column_name,
                relationship_type=relationship_model.relationship_type,  # type: ignore[arg-type]
                join_type=relationship_model.join_type,  # type: ignore[arg-type]
                business_meaning=relationship_model.business_meaning,
                join_priority=relationship_model.join_priority,  # type: ignore[arg-type]
                confidence=relationship_model.confidence,
                path_id=relationship_model.path_id,
            )
            relationships.append(relationship)

        for column_model in column_models:
            column = SemanticColumn(
                schema_name=column_model.schema_name,
                table_name=column_model.table_name,
                column_name=column_model.column_name,
                label=column_model.label,
                business_description=column_model.business_description,
                semantic_types=list(column_model.semantic_types or []),
                analytics_roles=list(column_model.analytics_roles or []),
                value_type=column_model.value_type,
                aggregation=list(column_model.aggregation or []),
                filterable=column_model.filterable,
                groupable=column_model.groupable,
                sortable=column_model.sortable,
                synonyms=list(column_model.synonyms or []),
                example_values=list(column_model.example_values or []),
                data_type=column_model.data_type,
                nullable=column_model.nullable,
                default_value=column_model.default_value,
                max_length=column_model.max_length,
                ordinal_position=column_model.ordinal_position,
                is_pk=column_model.is_pk,
                is_fk=column_model.is_fk,
                referenced_table=column_model.referenced_table,
                referenced_column=column_model.referenced_column,
                comment=column_model.comment,
                profile=ColumnProfile.model_validate(column_model.profile or {}),
            )
            key = (column.schema_name, column.table_name)
            table = table_map.get(key)
            if table is not None:
                table.columns.append(column)

        for table in tables:
            table.relationships = [rel for rel in relationships if rel.from_table == table.table_name]

        join_paths: list[SemanticJoinPath] = [
            SemanticJoinPath(
                path_id=path_model.path_id,
                from_table=path_model.from_table,
                to_table=path_model.to_table,
                joins=list(path_model.joins or []),
                business_use_case=path_model.business_use_case,
                tables=list(path_model.tables or []),
            )
            for path_model in join_path_models
        ]
        for table in tables:
            table.join_paths = [path for path in join_paths if path.from_table == table.table_name or path.to_table == table.table_name]

        return SemanticCatalog(
            database_id=catalog_model.database_id,
            dialect=catalog_model.dialect,
            tables=tables,
            relationships=relationships,
            join_paths=join_paths,
            relationship_graph=[RelationshipGraphEdge.model_validate(edge) for edge in list(catalog_model.relationship_graph or [])],
        )

    def _deactivate_catalogs(self, db: Session, database_id: str) -> None:
        db.query(SemanticCatalogModel).filter(SemanticCatalogModel.database_id == database_id).update(
            {SemanticCatalogModel.active: False},
            synchronize_session=False,
        )
        db.flush()

    def _latest_scan_run_id(self, db: Session, database_id: str) -> str | None:
        latest_scan = self.knowledge_service.get_summary(db, database_id).last_scan
        return latest_scan.id if latest_scan is not None else None

    def _relationship_schema(self, table_name: str, tables: list[SemanticTable]) -> str:
        for table in tables:
            if table.table_name == table_name:
                return table.schema_name
        return "public"

    def _catalog_notes(self, catalog: SemanticCatalog) -> list[str]:
        notes = [
            f"tables={len(catalog.tables)}",
            f"relationships={len(catalog.relationships)}",
            f"join_paths={len(catalog.join_paths)}",
            f"graph_edges={len(catalog.relationship_graph)}",
        ]
        if self.llm_service.configured:
            notes.append("enriched_with_llm")
        return notes

    def _apply_llm_enrichment(
        self,
        tables: list[SemanticTable],
        relationship_graph: list[RelationshipGraphEdge],
    ) -> list[SemanticTable]:
        if not self.llm_service.configured:
            return tables

        enriched_tables: list[SemanticTable] = []
        for table in tables:
            relationships = [rel.model_dump(mode="json") for rel in table.relationships]
            join_paths = [path.model_dump(mode="json") for path in table.join_paths]
            graph_edges = [
                edge.model_dump(mode="json")
                for edge in relationship_graph
                if edge.from_table == table.table_name or edge.to_table == table.table_name
            ]
            enrichment = self.llm_service.enrich_semantic_table(table, relationships, join_paths, graph_edges)
            if enrichment is None:
                enriched_tables.append(table)
                continue
            enriched_tables.append(self._merge_table_enrichment(table, enrichment))
        return enriched_tables

    def _merge_table_enrichment(
        self,
        table: SemanticTable,
        enrichment: SemanticTableEnrichment,
    ) -> SemanticTable:
        updated_columns = {column.column_name: column for column in table.columns}
        for column_enrichment in enrichment.columns:
            column = updated_columns.get(column_enrichment.column_name)
            if column is None:
                continue
            if column_enrichment.label:
                column.label = column_enrichment.label
            if column_enrichment.business_description:
                column.business_description = column_enrichment.business_description
            if column_enrichment.semantic_types:
                column.semantic_types = sorted({*column.semantic_types, *column_enrichment.semantic_types})
            if column_enrichment.analytics_roles:
                column.analytics_roles = sorted({*column.analytics_roles, *column_enrichment.analytics_roles})
            if column_enrichment.synonyms:
                column.synonyms = sorted({*column.synonyms, *column_enrichment.synonyms})

        update_payload: dict[str, Any] = {}
        if enrichment.label:
            update_payload["label"] = enrichment.label
        if enrichment.business_description:
            update_payload["business_description"] = enrichment.business_description
        if enrichment.table_role:
            update_payload["table_role"] = enrichment.table_role
        if enrichment.grain:
            update_payload["grain"] = enrichment.grain
        if enrichment.main_date_column:
            update_payload["main_date_column"] = enrichment.main_date_column
        if enrichment.main_entity:
            update_payload["main_entity"] = enrichment.main_entity
        if enrichment.synonyms:
            update_payload["synonyms"] = sorted({*table.synonyms, *enrichment.synonyms})
        if enrichment.important_metrics:
            update_payload["important_metrics"] = sorted({*table.important_metrics, *enrichment.important_metrics})
        if enrichment.important_dimensions:
            update_payload["important_dimensions"] = sorted({*table.important_dimensions, *enrichment.important_dimensions})
        return table.model_copy(update=update_payload)

    def _resolve_target(self, db: Session, database_id: str) -> dict[str, Any]:
        engine = resolve_engine(db, database_id)
        dialect = resolve_dialect(db, database_id)
        allowed_tables = set(resolve_allowed_tables(db, database_id, engine) or [])
        return {
            "engine": engine,
            "dialect": dialect,
            "table_keys": self._list_table_keys(engine, dialect, allowed_tables),
        }

    def _list_table_keys(self, engine: Any, dialect: str, allowed_tables: set[str]) -> list[tuple[str, str]]:
        inspector = sa_inspect(engine)
        try:
            schemas = inspector.get_schema_names()
        except Exception:  # noqa: BLE001
            schemas = []
        keys: list[tuple[str, str]] = []
        for schema_name in (str(schema) for schema in schemas if schema and not str(schema).startswith("pg_")):
            try:
                table_names = inspector.get_table_names(schema=schema_name)
            except Exception:  # noqa: BLE001
                table_names = []
            for table_name in table_names:
                if allowed_tables and table_name not in allowed_tables:
                    continue
                keys.append((schema_name, str(table_name)))
        if not keys:
            schema_name = "public" if str(dialect).startswith("postgres") else "main"
            try:
                table_names = inspector.get_table_names(schema=schema_name if schema_name == "public" else None)
            except Exception:  # noqa: BLE001
                table_names = []
            for table_name in table_names:
                if allowed_tables and table_name not in allowed_tables:
                    continue
                keys.append((schema_name, str(table_name)))
        return keys

    def _load_knowledge_tables(self, db: Session, database_id: str) -> dict[tuple[str, str], Any]:
        summary = self.knowledge_service.get_summary(db, database_id)
        result: dict[tuple[str, str], Any] = {}
        for table in summary.tables:
            try:
                loaded = self.knowledge_service.get_table_by_key(db, database_id, table.schema_name, table.table_name)
            except Exception:  # noqa: BLE001
                loaded = None
            if loaded is not None:
                result[(table.schema_name, table.table_name)] = loaded
        return result

    def _build_table(
        self,
        inspector: Any,
        engine: Any,
        schema_name: str,
        table_name: str,
        physical: Any | None,
    ) -> SemanticTable:
        columns_meta = self._safe_get_columns(inspector, schema_name, table_name)
        pk_constraint = self._safe_get_pk(inspector, schema_name, table_name)
        table_comment = self._safe_get_table_comment(inspector, schema_name, table_name)
        indexes = self._safe_get_indexes(inspector, schema_name, table_name)
        sample_rows = self._sample_rows(engine, schema_name, table_name)
        relationship_rows = self._safe_get_foreign_keys(inspector, schema_name, table_name)

        columns: list[SemanticColumn] = []
        relationships: list[SemanticRelationship] = []
        fk_lookup = {
            row["constrained_columns"][0]: row
            for row in relationship_rows
            if row.get("constrained_columns") and row.get("referred_table")
        }
        primary_key = [str(name) for name in (pk_constraint.get("constrained_columns") or []) if name]

        for ordinal, column in enumerate(columns_meta, start=1):
            column_name = str(column.get("name"))
            foreign_key = fk_lookup.get(column_name)
            profile = self._profile_column(column_name, sample_rows)
            semantic_types, analytics_roles, value_type, aggregation, filterable, groupable, sortable = self._infer_column_semantics(
                table_name=table_name,
                column_name=column_name,
                data_type=str(column.get("type")),
                profile=profile,
                is_pk=column_name in primary_key,
                foreign_key=foreign_key,
            )
            label = self._humanize(column_name)
            business_description = self._default_column_description(table_name, column_name)
            if column_name in primary_key:
                business_description = f"Primary key for {table_name}."
            if foreign_key:
                business_description = f"Foreign key to {foreign_key.get('referred_table')}."

            columns.append(
                SemanticColumn(
                    schema_name=schema_name,
                    table_name=table_name,
                    column_name=column_name,
                    label=label,
                    business_description=business_description,
                    semantic_types=semantic_types,
                    analytics_roles=analytics_roles,
                    value_type=value_type,
                    aggregation=aggregation,
                    filterable=filterable,
                    groupable=groupable,
                    sortable=sortable,
                    synonyms=self._column_synonyms(table_name, column_name, label),
                    example_values=profile.top_values[:5],
                    data_type=str(column.get("type")),
                    nullable=bool(column.get("nullable", True)),
                    default_value=self._stringify(column.get("default")),
                    max_length=self._max_length_from_type(str(column.get("type"))),
                    ordinal_position=ordinal,
                    is_pk=column_name in primary_key,
                    is_fk=foreign_key is not None,
                    referenced_table=str(foreign_key.get("referred_table")) if foreign_key else None,
                    referenced_column=str((foreign_key.get("referred_columns") or [None])[0]) if foreign_key else None,
                    comment=self._stringify(column.get("comment")),
                    profile=profile,
                )
            )

            if foreign_key:
                relationships.append(
                    self._build_relationship(
                        table_name=table_name,
                        column_name=column_name,
                        foreign_key=foreign_key,
                    )
                )

        row_count = self._safe_row_count(engine, schema_name, table_name)
        table_role = self._infer_table_role(table_name, columns, relationships, row_count)
        main_date_column = self._pick_main_date_column(columns)
        main_entity = self._humanize(table_name)
        important_metrics = [column.column_name for column in columns if "primary_metric" in column.analytics_roles or "metric" in column.semantic_types]
        important_dimensions = [
            column.column_name
            for column in columns
            if any(role in column.analytics_roles for role in ("default_group_by", "default_filter", "display_name", "time_axis"))
        ]

        return SemanticTable(
            schema_name=schema_name,
            table_name=table_name,
            label=self._humanize(table_name),
            business_description=self._default_table_description(table_name),
            table_role=table_role,
            grain=self._infer_grain(table_name, columns),
            main_date_column=main_date_column,
            main_entity=main_entity,
            synonyms=self._table_synonyms(table_name),
            important_metrics=important_metrics,
            important_dimensions=important_dimensions,
            row_count_estimate=row_count,
            primary_key=primary_key,
            foreign_keys=relationships,
            indexes=indexes,
            comment=table_comment,
            columns=columns,
            relationships=relationships,
        )

    def _profile_column(self, column_name: str, sample_rows: list[dict[str, Any]]) -> ColumnProfile:
        values = [row.get(column_name) for row in sample_rows if row.get(column_name) is not None]
        total = len(sample_rows)
        distinct_values = [self._normalize_value(value) for value in values]
        distinct = [value for value in distinct_values if value is not None]
        null_ratio = None if total == 0 else round((total - len(values)) / total, 4)
        avg_length = None
        if values:
            lengths = [len(str(value)) for value in values]
            avg_length = round(mean(lengths), 2)
        top_values = [value for value, _count in Counter(distinct).most_common(5)]
        uniqueness_ratio = None if total == 0 else round(len(set(distinct)) / total, 4)
        numeric_values = self._coerce_numeric(values)
        numeric_mean = round(mean(numeric_values), 4) if numeric_values else None
        numeric_min = round(min(numeric_values), 4) if numeric_values else None
        numeric_max = round(max(numeric_values), 4) if numeric_values else None
        return ColumnProfile(
            distinct_count=len(set(distinct)),
            null_ratio=null_ratio,
            min_value=self._stringify(min(values)) if values and self._all_comparable(values) else None,
            max_value=self._stringify(max(values)) if values and self._all_comparable(values) else None,
            avg_length=avg_length,
            top_values=top_values,
            uniqueness_ratio=uniqueness_ratio,
            numeric_mean=numeric_mean,
            numeric_min=numeric_min,
            numeric_max=numeric_max,
        )

    def _infer_column_semantics(
        self,
        *,
        table_name: str,
        column_name: str,
        data_type: str,
        profile: ColumnProfile,
        is_pk: bool,
        foreign_key: dict[str, Any] | None,
    ) -> tuple[list[SemanticType], list[AnalyticsRole], str | None, list[str], bool, bool, bool]:
        name = column_name.lower()
        data_type_lower = data_type.lower()
        semantic_types: list[SemanticType] = []
        analytics_roles: list[AnalyticsRole] = []
        aggregation: list[str] = []

        if is_pk:
            semantic_types.append("id")
            analytics_roles.append("display_name")
            return semantic_types, analytics_roles, "identifier", ["count", "count_distinct"], True, True, True

        if foreign_key is not None or name.endswith("_id"):
            semantic_types.append("foreign_key")
            analytics_roles.append("default_filter")
            return semantic_types, analytics_roles, "identifier", ["count", "count_distinct"], True, True, True

        if self._looks_like_datetime(name, data_type_lower):
            semantic_types.append("datetime")
            analytics_roles.append("time_axis")
            return semantic_types, analytics_roles, "datetime", ["min", "max", "count"], True, True, True

        if self._looks_like_boolean(name, data_type_lower):
            semantic_types.append("boolean_flag")
            analytics_roles.append("default_filter")
            return semantic_types, analytics_roles, "boolean", ["count", "count_distinct"], True, True, True

        if self._looks_like_ratio(name, data_type_lower):
            semantic_types.append("ratio")
            analytics_roles.append("supporting_metric")
            return semantic_types, analytics_roles, "ratio", ["avg", "min", "max"], True, False, True

        if self._looks_like_duration(name, data_type_lower):
            semantic_types.append("duration")
            analytics_roles.append("supporting_metric")
            return semantic_types, analytics_roles, "duration", ["avg", "min", "max"], True, False, True

        if self._looks_like_metric(name, data_type_lower):
            semantic_types.append("metric")
            value_type = "currency" if any(hint in name for hint in _METRIC_NAME_HINTS) else "numeric"
            if "currency" in value_type:
                semantic_types.append("currency")
            analytics_roles.append("primary_metric")
            if any(hint in name for hint in _COUNT_NAME_HINTS):
                return semantic_types, analytics_roles, value_type, ["count", "count_distinct"], True, False, True
            return semantic_types, analytics_roles, value_type, ["sum", "avg", "min", "max"], True, False, True

        if any(hint in name for hint in _LOCATION_HINTS):
            semantic_types.append("location")
            analytics_roles.append("default_group_by")
            return semantic_types, analytics_roles, "location", ["count", "count_distinct"], True, True, True

        if any(hint in name for hint in _STATUS_HINTS):
            semantic_types.append("status")
            analytics_roles.append("default_filter")
            return semantic_types, analytics_roles, "status", ["count", "count_distinct"], True, True, True

        if any(hint in name for hint in _NAME_HINTS):
            semantic_types.append("name")
            analytics_roles.append("display_name")
            return semantic_types, analytics_roles, "string", ["count", "count_distinct"], True, True, True

        if self._looks_like_category(name, data_type_lower, profile):
            semantic_types.append("category")
            analytics_roles.append("default_group_by")
            return semantic_types, analytics_roles, "category", ["count", "count_distinct"], True, True, True

        semantic_types.append("text")
        analytics_roles.append("display_name" if profile.uniqueness_ratio and profile.uniqueness_ratio > 0.9 else "default_group_by")
        return semantic_types, analytics_roles, "text", ["count", "count_distinct"], True, True, True

    def _infer_table_role(
        self,
        table_name: str,
        columns: list[SemanticColumn],
        relationships: list[SemanticRelationship],
        row_count: int | None,
    ) -> TableRole:
        name = table_name.lower()
        if any(hint in name for hint in ("bridge", "junction", "link", "map")):
            return "bridge"
        fk_count = sum(1 for column in columns if column.is_fk)
        metric_count = sum(1 for column in columns if "metric" in column.semantic_types or "currency" in column.semantic_types)
        time_count = sum(1 for column in columns if "datetime" in column.semantic_types)
        if fk_count >= 2 and metric_count == 0 and len(columns) <= 6:
            return "bridge"
        if metric_count >= 1 and time_count >= 1:
            return "fact"
        if any(hint in name for hint in ("fact", "payment", "order", "transaction", "event", "sale", "booking")):
            return "fact"
        if time_count >= 1 and row_count is not None and row_count > 0:
            return "event"
        if any(hint in name for hint in ("dim_", "_dim", "dimension", "lookup", "ref", "status", "category")):
            return "dimension"
        if fk_count == 0 and len(columns) <= 4:
            return "lookup"
        if metric_count == 0 and fk_count <= 1:
            return "dimension"
        return "snapshot"

    def _infer_grain(self, table_name: str, columns: list[SemanticColumn]) -> str:
        if any(column.is_pk for column in columns):
            main = next((column for column in columns if "datetime" in column.semantic_types), None)
            if main is not None:
                return f"one row = one {self._humanize(table_name).rstrip('s').lower()} event"
        if any(column.is_fk for column in columns):
            return f"one row = one {self._humanize(table_name).rstrip('s').lower()} relationship"
        return f"one row = one {self._humanize(table_name).rstrip('s').lower()}"

    def _pick_main_date_column(self, columns: list[SemanticColumn]) -> str | None:
        for column in columns:
            if "time_axis" in column.analytics_roles or "datetime" in column.semantic_types:
                return column.column_name
        return None

    def _build_relationship(self, table_name: str, column_name: str, foreign_key: dict[str, Any]) -> SemanticRelationship:
        referred_table = str(foreign_key.get("referred_table"))
        relationship_type = "many-to-one"
        if table_name == referred_table:
            relationship_type = "one-to-one"
        elif any(hint in table_name.lower() for hint in ("bridge", "junction", "link")):
            relationship_type = "junction"
        business_meaning = f"Each {self._humanize(table_name, plural=False)} belongs to one {self._humanize(referred_table, plural=False)}."
        return SemanticRelationship(
            from_table=table_name,
            from_column=column_name,
            to_table=referred_table,
            to_column=str((foreign_key.get("referred_columns") or [None])[0]),
            relationship_type=relationship_type,  # type: ignore[arg-type]
            join_type="inner",
            business_meaning=business_meaning,
            join_priority="high",
            confidence=1.0,
        )

    def _build_join_paths(self, tables: list[SemanticTable], relationships: list[SemanticRelationship]) -> list[SemanticJoinPath]:
        graph: dict[str, list[SemanticRelationship]] = defaultdict(list)
        for relationship in relationships:
            graph[relationship.from_table].append(relationship)
            reverse = relationship.model_copy(update={"from_table": relationship.to_table, "to_table": relationship.from_table, "from_column": relationship.to_column, "to_column": relationship.from_column})
            graph[reverse.from_table].append(reverse)

        paths: list[SemanticJoinPath] = []
        table_roles = {table.table_name: table.table_role for table in tables}
        for source in tables:
            for target in tables:
                if source.table_name == target.table_name:
                    continue
                path = self._find_path(graph, source.table_name, target.table_name)
                if not path:
                    continue
                joins = [
                    f"{step.from_table}.{step.from_column} = {step.to_table}.{step.to_column}"
                    for step in path
                ]
                use_case = self._build_join_use_case(source.table_name, target.table_name, table_roles)
                paths.append(
                    SemanticJoinPath(
                        path_id=f"{source.table_name}_to_{target.table_name}",
                        from_table=source.table_name,
                        to_table=target.table_name,
                        joins=joins,
                        business_use_case=use_case,
                        tables=self._path_tables(source.table_name, target.table_name, path),
                    )
                )
        return self._dedupe_paths(paths)

    def _find_path(self, graph: dict[str, list[SemanticRelationship]], start: str, goal: str) -> list[SemanticRelationship] | None:
        queue: deque[tuple[str, list[SemanticRelationship]]] = deque([(start, [])])
        visited = {start}
        while queue:
            table_name, path = queue.popleft()
            if len(path) > 5:
                continue
            for edge in graph.get(table_name, []):
                if edge.to_table in visited:
                    continue
                next_path = [*path, edge]
                if edge.to_table == goal:
                    return next_path
                visited.add(edge.to_table)
                queue.append((edge.to_table, next_path))
        return None

    def _build_join_use_case(
        self,
        source_table: str,
        target_table: str,
        table_roles: dict[str, TableRole],
    ) -> str:
        source_role = table_roles.get(source_table, "dimension")
        target_role = table_roles.get(target_table, "dimension")
        if source_role == "fact" and target_role == "dimension":
            return f"Analyze {self._humanize(source_table, plural=False)} by {self._humanize(target_table, plural=False)}."
        if target_role == "fact" and source_role == "dimension":
            return f"Analyze {self._humanize(target_table, plural=False)} by {self._humanize(source_table, plural=False)}."
        return f"Join {self._humanize(source_table)} with {self._humanize(target_table)}."

    def _path_tables(self, source_table: str, target_table: str, path: list[SemanticRelationship]) -> list[str]:
        tables = [source_table]
        for relationship in path:
            if relationship.to_table not in tables:
                tables.append(relationship.to_table)
        if target_table not in tables:
            tables.append(target_table)
        return tables

    def _dedupe_paths(self, paths: list[SemanticJoinPath]) -> list[SemanticJoinPath]:
        seen: set[str] = set()
        results: list[SemanticJoinPath] = []
        for path in paths:
            if path.path_id in seen:
                continue
            seen.add(path.path_id)
            results.append(path)
        return results

    def _expand_related_tables(
        self,
        seed_tables: list[SemanticTable],
        all_tables: list[SemanticTable],
        relationships: list[SemanticRelationship],
        *,
        limit: int = 5,
    ) -> list[SemanticTable]:
        all_table_map = {table.table_name: table for table in all_tables}
        selected = {table.table_name: table for table in seed_tables[:limit]}
        queue = list(seed_tables)
        while queue and len(selected) < limit:
            current = queue.pop(0)
            for rel in relationships:
                neighbor = None
                if rel.from_table == current.table_name:
                    neighbor = rel.to_table
                elif rel.to_table == current.table_name:
                    neighbor = rel.from_table
                if not neighbor or neighbor in selected:
                    continue
                table = all_table_map.get(neighbor)
                if table is None:
                    continue
                selected[neighbor] = table
                queue.append(table)
                if len(selected) >= limit:
                    break
        return list(selected.values())

    def _score_table(self, table: SemanticTable, tokens: list[str]) -> float:
        haystack = " ".join(
            [
                table.table_name,
                table.label,
                table.business_description,
                " ".join(table.synonyms),
                " ".join(table.important_metrics),
                " ".join(table.important_dimensions),
                " ".join(column.column_name for column in table.columns),
                " ".join(token for column in table.columns for token in column.synonyms),
            ]
        )
        return self._text_score(haystack, tokens)

    def _score_column(self, column: SemanticColumn, tokens: list[str]) -> float:
        haystack = " ".join(
            [
                column.column_name,
                column.label,
                column.business_description,
                " ".join(column.synonyms),
                " ".join(str(value) for value in column.example_values),
            ]
        )
        return self._text_score(haystack, tokens)

    def _text_score(self, text: str, tokens: list[str]) -> float:
        lowered = text.lower()
        if not tokens:
            return 0.0
        score = 0.0
        for token in tokens:
            if token and token in lowered:
                score += 1.0
        return score / max(len(tokens), 1)

    def _catalog_to_schema(
        self,
        database_id: str,
        dialect: str,
        tables: list[SemanticTable],
        join_paths: list[SemanticJoinPath],
        relationship_graph: list[RelationshipGraphEdge],
    ) -> SchemaMetadataResponse:
        relationships = []
        for table in tables:
            for relationship in table.relationships:
                relationships.append(
                    RelationshipMetadata(
                        from_table=relationship.from_table,
                        from_column=relationship.from_column,
                        to_table=relationship.to_table,
                        to_column=relationship.to_column,
                        relation_type=relationship.relationship_type,
                        cardinality=relationship.relationship_type,
                    )
                )
        return SchemaMetadataResponse(
            database_id=database_id,
            dialect=dialect,
            tables=[
                TableMetadata(
                    name=table.table_name,
                    columns=[
                        ColumnMetadata(name=column.column_name, type=column.data_type)
                        for column in table.columns
                    ],
                )
                for table in tables
            ],
            relationships=relationships,
            relationship_graph=relationship_graph,
        )

    def _catalog_to_dictionary_entries(
        self,
        tables: list[SemanticTable],
        join_paths: list[SemanticJoinPath],
    ) -> list[DictionaryEntryRead]:
        entries: list[DictionaryEntryRead] = []
        for table in tables:
            entries.extend(self._table_dictionary_entries(table))
            for column in table.columns:
                entries.extend(self._column_dictionary_entries(table, column))
        entries.extend(self._join_path_dictionary_entries(join_paths))
        unique: dict[str, DictionaryEntryRead] = {}
        for entry in entries:
            unique[entry.term.lower()] = entry
        return list(unique.values())

    def _table_dictionary_entries(self, table: SemanticTable) -> list[DictionaryEntryRead]:
        return [
            DictionaryEntryRead.model_validate(
                {
                    "id": f"{table.schema_name}.{table.table_name}",
                    "term": table.table_name,
                    "synonyms": table.synonyms,
                    "mapped_expression": table.table_name,
                    "description": table.business_description,
                    "object_type": "table",
                    "table_name": table.table_name,
                    "source_database": None,
                    "column_name": None,
                }
            )
        ]

    def _column_dictionary_entries(self, table: SemanticTable, column: SemanticColumn) -> list[DictionaryEntryRead]:
        entries: list[DictionaryEntryRead] = []
        mapped_expression = f"{table.table_name}.{column.column_name}"
        if "primary_metric" in column.analytics_roles or "metric" in column.semantic_types:
            aggregation = "SUM" if "currency" in column.semantic_types or column.value_type in {"currency", "numeric"} else "COUNT"
            entries.append(
                DictionaryEntryRead.model_validate(
                    {
                        "id": f"{table.schema_name}.{table.table_name}.{column.column_name}.metric",
                        "term": column.label.lower().replace(" ", "_"),
                        "synonyms": column.synonyms + [column.column_name],
                        "mapped_expression": f"{aggregation}({mapped_expression})",
                        "description": column.business_description,
                        "object_type": "metric",
                        "table_name": table.table_name,
                        "column_name": column.column_name,
                        "source_database": None,
                    }
                )
            )
        if column.groupable or "time_axis" in column.analytics_roles or "display_name" in column.analytics_roles or "default_group_by" in column.analytics_roles:
            entries.append(
                DictionaryEntryRead.model_validate(
                    {
                        "id": f"{table.schema_name}.{table.table_name}.{column.column_name}.dimension",
                        "term": column.column_name,
                        "synonyms": column.synonyms + [column.label],
                        "mapped_expression": mapped_expression,
                        "description": column.business_description,
                        "object_type": "column",
                        "table_name": table.table_name,
                        "column_name": column.column_name,
                        "source_database": None,
                    }
                )
            )
        return entries

    def _join_path_dictionary_entries(self, join_paths: list[SemanticJoinPath]) -> list[DictionaryEntryRead]:
        entries: list[DictionaryEntryRead] = []
        for path in join_paths:
            entries.append(
                DictionaryEntryRead.model_validate(
                    {
                        "id": path.path_id,
                        "term": path.path_id,
                        "synonyms": [path.business_use_case],
                        "mapped_expression": " AND ".join(path.joins),
                        "description": path.business_use_case,
                        "object_type": "relationship",
                        "table_name": path.from_table,
                        "column_name": None,
                        "source_database": None,
                    }
                )
            )
        return entries

    def _merge_dictionary_entries(
        self,
        base: list[DictionaryEntryRead],
        generated: list[DictionaryEntryRead],
        selected_columns: set[str],
    ) -> list[DictionaryEntryRead]:
        merged: dict[str, DictionaryEntryRead] = {}
        for entry in [*base, *generated]:
            merged[entry.term.lower()] = entry
        # promote selected columns to the front by keeping their entries if present
        ordered: list[DictionaryEntryRead] = []
        for term, entry in merged.items():
            if any(f"{entry.table_name}.{entry.column_name}" == ref for ref in selected_columns if entry.column_name):
                ordered.append(entry)
            else:
                ordered.append(entry)
        return ordered

    def _build_notes(self, tables: list[SemanticTable], join_paths: list[SemanticJoinPath]) -> list[str]:
        notes: list[str] = []
        for table in tables:
            notes.append(f"{table.table_name}: role={table.table_role}, rows~{table.row_count_estimate}")
        if join_paths:
            notes.append(f"join_paths={len(join_paths)}")
        return notes

    def _safe_get_columns(self, inspector: Any, schema_name: str, table_name: str) -> list[dict[str, Any]]:
        try:
            return list(inspector.get_columns(table_name, schema=schema_name))
        except Exception:  # noqa: BLE001
            return []

    def _safe_get_pk(self, inspector: Any, schema_name: str, table_name: str) -> dict[str, Any]:
        try:
            return inspector.get_pk_constraint(table_name, schema=schema_name) or {}
        except Exception:  # noqa: BLE001
            return {}

    def _safe_get_indexes(self, inspector: Any, schema_name: str, table_name: str) -> list[dict[str, Any]]:
        try:
            return list(inspector.get_indexes(table_name, schema=schema_name))
        except Exception:  # noqa: BLE001
            return []

    def _safe_get_table_comment(self, inspector: Any, schema_name: str, table_name: str) -> str | None:
        try:
            comment = inspector.get_table_comment(table_name, schema=schema_name) or {}
        except Exception:  # noqa: BLE001
            return None
        return self._stringify(comment.get("text"))

    def _safe_get_foreign_keys(self, inspector: Any, schema_name: str, table_name: str) -> list[dict[str, Any]]:
        try:
            return list(inspector.get_foreign_keys(table_name, schema=schema_name))
        except Exception:  # noqa: BLE001
            return []

    def _sample_rows(self, engine: Any, schema_name: str, table_name: str, limit: int = 200) -> list[dict[str, Any]]:
        try:
            table = Table(table_name, MetaData(), schema=schema_name, autoload_with=engine)
            with engine.connect() as connection:
                rows = connection.execute(select(table).limit(limit)).mappings().all()
            return [dict(row) for row in rows]
        except Exception:  # noqa: BLE001
            return []

    def _safe_row_count(self, engine: Any, schema_name: str, table_name: str) -> int | None:
        try:
            table = Table(table_name, MetaData(), schema=schema_name, autoload_with=engine)
            with engine.connect() as connection:
                return int(connection.execute(select(func.count()).select_from(table)).scalar_one())
        except Exception:  # noqa: BLE001
            return None

    def _looks_like_datetime(self, name: str, data_type: str) -> bool:
        return "date" in data_type or "time" in data_type or any(hint in name for hint in _TIME_NAME_HINTS)

    def _looks_like_boolean(self, name: str, data_type: str) -> bool:
        return "bool" in data_type or name.startswith("is_") or name.startswith("has_") or name.startswith("flag")

    def _looks_like_ratio(self, name: str, data_type: str) -> bool:
        return any(hint in name for hint in _RATIO_HINTS) or "numeric" in data_type and any(hint in name for hint in _RATIO_HINTS)

    def _looks_like_duration(self, name: str, data_type: str) -> bool:
        return any(hint in name for hint in _DURATION_HINTS)

    def _looks_like_metric(self, name: str, data_type: str) -> bool:
        return "int" in data_type or "numeric" in data_type or "decimal" in data_type or "float" in data_type or any(hint in name for hint in _METRIC_NAME_HINTS + _COUNT_NAME_HINTS)

    def _looks_like_category(self, name: str, data_type: str, profile: ColumnProfile) -> bool:
        if "char" in data_type or "text" in data_type or "varchar" in data_type:
            if profile.uniqueness_ratio is not None and profile.uniqueness_ratio < 0.3:
                return True
            return not any(hint in name for hint in _NAME_HINTS)
        if profile.distinct_count is not None and profile.distinct_count <= 20:
            return True
        return False

    def _column_synonyms(self, table_name: str, column_name: str, label: str) -> list[str]:
        tokens = {column_name, label, f"{table_name}.{column_name}", column_name.replace("_", " "), label.lower()}
        tokens.add(column_name.replace("_id", ""))
        return sorted({token.strip() for token in tokens if token and token.strip()})

    def _table_synonyms(self, table_name: str) -> list[str]:
        tokens = {table_name, table_name.replace("_", " "), self._humanize(table_name), self._humanize(table_name, plural=False)}
        return sorted({token.strip() for token in tokens if token and token.strip()})

    def _humanize(self, value: str, *, plural: bool = True) -> str:
        cleaned = value.replace("_", " ").strip()
        if not cleaned:
            return value
        label = " ".join(part for part in cleaned.split() if part)
        return label.title() if plural else label.title().rstrip("S")

    def _default_table_description(self, table_name: str) -> str:
        return f"Physical table {table_name.replace('_', ' ')}."

    def _default_column_description(self, table_name: str, column_name: str) -> str:
        return f"Column {column_name} in {table_name}."

    def _stringify(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _normalize_value(self, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return value
        text = str(value).strip()
        return text or None

    def _coerce_numeric(self, values: list[Any]) -> list[float]:
        numeric: list[float] = []
        for value in values:
            if isinstance(value, bool) or value is None:
                continue
            try:
                numeric.append(float(value))
                continue
            except Exception:
                pass
            try:
                numeric.append(float(str(value).replace(",", ".")))
            except Exception:
                continue
        return numeric

    def _all_comparable(self, values: list[Any]) -> bool:
        try:
            sorted(values)
            return True
        except Exception:  # noqa: BLE001
            return False

    def _max_length_from_type(self, data_type: str) -> int | None:
        match = re.search(r"\((\d+)\)", data_type)
        return int(match.group(1)) if match else None

    def _build_relationship_from_row(self, row: dict[str, Any]) -> SemanticRelationship:
        return SemanticRelationship(
            from_table=str(row.get("from_table") or ""),
            from_column=str(row.get("from_column") or ""),
            to_table=str(row.get("to_table") or ""),
            to_column=str(row.get("to_column") or ""),
            relationship_type="many-to-one",
            join_type="inner",
            business_meaning="",
            join_priority="medium",
            confidence=0.0,
        )
