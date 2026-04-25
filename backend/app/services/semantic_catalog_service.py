from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict, deque
from statistics import mean
from typing import Any

from sqlalchemy import MetaData, Table, func, inspect as sa_inspect, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.dictionary import DictionaryEntryRead
from app.schemas.metadata import ColumnMetadata, RelationshipGraphEdge, RelationshipMetadata, SchemaMetadataResponse, TableMetadata
from app.schemas.query import IntentPayload
from app.schemas.semantic_catalog import (
    AnalyticsRole,
    ColumnProfile,
    SemanticColumnDescription,
    SemanticCatalog,
    SemanticCatalogActivationRequest,
    SemanticColumn,
    SemanticColumnPatch,
    SemanticRelationshipDescription,
    SemanticJoinPath,
    SemanticRelationship,
    SemanticIntentResolution,
    SemanticRetrievalContext,
    SemanticTable,
    SemanticTermCandidate,
    SemanticTermResolutionItem,
    SemanticTableEnrichment,
    SemanticTablePatch,
    SemanticType,
    TableRole,
    SemanticTableDescription,
)
from app.db.models import (
    DatabaseKnowledgeColumnModel,
    DatabaseKnowledgeRelationshipModel,
    DatabaseKnowledgeTableModel,
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
from app.services.schema_fact_builder import SchemaFactBuilder
from app.services.semantic_rule_engine import SemanticRuleEngine
from app.services.semantic_validator import SemanticValidator


_METRIC_NAME_HINTS = ("amount", "revenue", "sales", "price", "cost", "fee", "profit", "balance", "value")
_COUNT_NAME_HINTS = ("count", "qty", "quantity", "total", "num", "number")
_TIME_NAME_HINTS = ("created_at", "updated_at", "date", "time", "timestamp", "month", "day", "week", "year")
_NAME_HINTS = ("name", "title", "label", "description", "display", "full_name")
_STATUS_HINTS = ("status", "state", "stage", "phase")
_LOCATION_HINTS = ("city", "country", "region", "state", "location", "address", "postal", "zip")
_RATIO_HINTS = ("rate", "ratio", "pct", "percent", "percentage")
_DURATION_HINTS = ("duration", "elapsed", "minutes", "hours", "days", "seconds")


class SemanticCatalogService:
    TEMPORAL_DIMENSION_TERMS = {"hour", "day", "week", "month", "quarter", "year"}

    def __init__(self) -> None:
        self.knowledge_service = KnowledgeService()
        self.llm_service = LLMService()
        self.schema_fact_builder = SchemaFactBuilder()
        self.semantic_rule_engine = SemanticRuleEngine()
        self.semantic_validator = SemanticValidator()

    def get_catalog(
        self,
        db: Session,
        database_id: str,
        *,
        refresh: bool = False,
        database_description: str | None = None,
    ) -> SemanticCatalog:
        effective_database_description = self._effective_database_description(
            db,
            database_id,
            database_description,
        )
        if not refresh:
            cached = self._load_active_catalog(db, database_id)
            if cached is not None:
                return cached

        catalog = self.build_catalog(
            db,
            database_id,
            database_description=effective_database_description,
        )
        return self.save_catalog(
            db,
            catalog,
            database_description=effective_database_description,
        )

    def activate_catalog(
        self,
        db: Session,
        database_id: str,
        *,
        refresh: bool = False,
        database_description: str | None = None,
        table_descriptions: list[SemanticTableDescription] | None = None,
        relationship_descriptions: list[SemanticRelationshipDescription] | None = None,
        column_descriptions: list[SemanticColumnDescription] | None = None,
    ) -> SemanticCatalog:
        if database_description is not None:
            self.knowledge_service.set_database_description(db, database_id, database_description)
        if table_descriptions or relationship_descriptions or column_descriptions:
            self._persist_manual_descriptions(
                db,
                database_id,
                table_descriptions=table_descriptions or [],
                relationship_descriptions=relationship_descriptions or [],
                column_descriptions=column_descriptions or [],
            )
        effective_database_description = self._effective_database_description(
            db,
            database_id,
            database_description,
        )
        has_manual_input = any(
            [
                (effective_database_description or "").strip(),
                bool(table_descriptions),
                bool(relationship_descriptions),
                bool(column_descriptions),
            ]
        )
        cached = self._load_active_catalog(db, database_id)
        if cached is not None and not refresh and not has_manual_input:
            return cached
        catalog = self.build_catalog(
            db,
            database_id,
            database_description=effective_database_description,
        )
        effective_overrides = self._merge_descriptions(
            cached if cached is not None else catalog,
            table_descriptions=[],
            relationship_descriptions=[],
            column_descriptions=[],
        )
        overrides = self._merge_descriptions(
            catalog,
            table_descriptions=table_descriptions or [],
            relationship_descriptions=relationship_descriptions or [],
            column_descriptions=column_descriptions or [],
        )
        for section in ("tables", "relationships", "columns"):
            effective_overrides[section].update(overrides[section])
        if any(effective_overrides.values()):
            catalog = self._apply_manual_descriptions(catalog, effective_overrides)
        return self.save_catalog(db, catalog, database_description=effective_database_description)

    def save_catalog(
        self,
        db: Session,
        catalog: SemanticCatalog,
        database_description: str | None = None,
    ) -> SemanticCatalog:
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
            notes=self._catalog_notes(
                catalog,
                database_description=database_description,
            ),
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

    def build_catalog(
        self,
        db: Session,
        database_id: str,
        database_description: str | None = None,
    ) -> SemanticCatalog:
        target = self._resolve_target(db, database_id)
        inspector = sa_inspect(target["engine"])
        language_hint = self._detect_language(database_description)
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
                language_hint=language_hint,
            )
            tables.append(table)
            relationships.extend(table.relationships)

        join_paths = self._build_join_paths(tables, relationships)
        relationship_graph = build_relationship_graph(relationships)
        for table in tables:
            table.join_paths = [path for path in join_paths if path.from_table == table.table_name or path.to_table == table.table_name]
        tables = self._apply_llm_enrichment(
            tables,
            relationship_graph,
            database_description=database_description,
        )

        return SemanticCatalog(
            database_id=database_id,
            dialect=target["dialect"],
            tables=tables,
            relationships=relationships,
            join_paths=join_paths,
            relationship_graph=relationship_graph,
        )

    def delete_active_catalog(self, db: Session, database_id: str) -> bool:
        deleted = (
            db.query(SemanticCatalogModel)
            .filter(
                SemanticCatalogModel.database_id == database_id,
                SemanticCatalogModel.active.is_(True),
            )
            .first()
        )
        if deleted is None:
            return False
        deleted.active = False
        db.commit()
        return True

    def _effective_database_description(
        self,
        db: Session,
        database_id: str,
        database_description: str | None,
    ) -> str | None:
        explicit = (database_description or "").strip()
        if explicit:
            return explicit
        metadata = self.knowledge_service.get_database_metadata(db, database_id)
        if metadata is None:
            return None
        stored = (metadata.description_manual or "").strip()
        return stored or None

    def _persist_manual_descriptions(
        self,
        db: Session,
        database_id: str,
        *,
        table_descriptions: list[SemanticTableDescription],
        relationship_descriptions: list[SemanticRelationshipDescription],
        column_descriptions: list[SemanticColumnDescription],
    ) -> None:
        for item in table_descriptions:
            table = (
                db.query(DatabaseKnowledgeTableModel)
                .filter(
                    DatabaseKnowledgeTableModel.database_id == database_id,
                    DatabaseKnowledgeTableModel.table_name == item.table_name.strip(),
                )
                .first()
            )
            if table is not None:
                table.description_manual = item.business_description.strip()

        for item in column_descriptions:
            column = (
                db.query(DatabaseKnowledgeColumnModel)
                .filter(
                    DatabaseKnowledgeColumnModel.database_id == database_id,
                    DatabaseKnowledgeColumnModel.table_name == item.table_name.strip(),
                    DatabaseKnowledgeColumnModel.column_name == item.column_name.strip(),
                )
                .first()
            )
            if column is not None:
                column.description_manual = item.business_description.strip()

        for item in relationship_descriptions:
            from_table_model = (
                db.query(DatabaseKnowledgeTableModel)
                .filter(
                    DatabaseKnowledgeTableModel.database_id == database_id,
                    DatabaseKnowledgeTableModel.table_name == item.from_table.strip(),
                )
                .first()
            )
            to_table_model = (
                db.query(DatabaseKnowledgeTableModel)
                .filter(
                    DatabaseKnowledgeTableModel.database_id == database_id,
                    DatabaseKnowledgeTableModel.table_name == item.to_table.strip(),
                )
                .first()
            )
            from_schema = from_table_model.schema_name if from_table_model is not None else "public"
            to_schema = to_table_model.schema_name if to_table_model is not None else "public"
            relationship = (
                db.query(DatabaseKnowledgeRelationshipModel)
                .filter(
                    DatabaseKnowledgeRelationshipModel.database_id == database_id,
                    DatabaseKnowledgeRelationshipModel.from_table_name == item.from_table.strip(),
                    DatabaseKnowledgeRelationshipModel.from_column_name == item.from_column.strip(),
                    DatabaseKnowledgeRelationshipModel.to_table_name == item.to_table.strip(),
                    DatabaseKnowledgeRelationshipModel.to_column_name == item.to_column.strip(),
                )
                .first()
            )
            if relationship is not None:
                relationship.description_manual = item.business_meaning.strip()
                relationship.from_schema_name = from_schema
                relationship.to_schema_name = to_schema
            else:
                db.add(
                    DatabaseKnowledgeRelationshipModel(
                        database_id=database_id,
                        from_schema_name=from_schema,
                        from_table_name=item.from_table.strip(),
                        from_column_name=item.from_column.strip(),
                        to_schema_name=to_schema,
                        to_table_name=item.to_table.strip(),
                        to_column_name=item.to_column.strip(),
                        relation_type="manual",
                        description_manual=item.business_meaning.strip(),
                        confidence=1.0,
                        approved=True,
                    )
                )

        db.commit()

    def patch_catalog_table(
        self,
        db: Session,
        database_id: str,
        table_name: str,
        patch: SemanticTablePatch,
    ) -> SemanticTable | None:
        knowledge_model = (
            db.query(DatabaseKnowledgeTableModel)
            .filter(
                DatabaseKnowledgeTableModel.database_id == database_id,
                DatabaseKnowledgeTableModel.table_name == table_name,
            )
            .first()
        )
        model = (
            db.query(SemanticCatalogTableModel)
            .join(SemanticCatalogModel, SemanticCatalogTableModel.catalog_id == SemanticCatalogModel.id)
            .filter(
                SemanticCatalogTableModel.database_id == database_id,
                SemanticCatalogTableModel.table_name == table_name,
                SemanticCatalogModel.active.is_(True),
            )
            .first()
        )
        if model is None and knowledge_model is None:
            return None
        if patch.label is not None:
            if model is not None:
                model.label = patch.label
            if knowledge_model is not None:
                knowledge_model.semantic_label_manual = patch.label
        if patch.business_description is not None:
            if model is not None:
                model.business_description = patch.business_description
            if knowledge_model is not None:
                knowledge_model.description_manual = patch.business_description
        if patch.table_role is not None:
            if model is not None:
                model.table_role = patch.table_role
            if knowledge_model is not None:
                knowledge_model.semantic_table_role_manual = patch.table_role
        if patch.grain is not None:
            if model is not None:
                model.grain = patch.grain
            if knowledge_model is not None:
                knowledge_model.semantic_grain_manual = patch.grain
        if patch.main_date_column is not None:
            if model is not None:
                model.main_date_column = patch.main_date_column
            if knowledge_model is not None:
                knowledge_model.semantic_main_date_column_manual = patch.main_date_column
        if patch.main_entity is not None:
            if model is not None:
                model.main_entity = patch.main_entity
            if knowledge_model is not None:
                knowledge_model.semantic_main_entity_manual = patch.main_entity
        if patch.synonyms is not None:
            if model is not None:
                model.synonyms = patch.synonyms
            if knowledge_model is not None:
                knowledge_model.semantic_synonyms = list(patch.synonyms)
        if patch.important_metrics is not None:
            if model is not None:
                model.important_metrics = patch.important_metrics
            if knowledge_model is not None:
                knowledge_model.semantic_important_metrics = list(patch.important_metrics)
        if patch.important_dimensions is not None:
            if model is not None:
                model.important_dimensions = patch.important_dimensions
            if knowledge_model is not None:
                knowledge_model.semantic_important_dimensions = list(patch.important_dimensions)
        if model is not None and model.table_role == "fact" and not str(model.grain or "").strip():
            model.grain = self._fallback_grain(model.table_name)
        if (
            knowledge_model is not None
            and knowledge_model.semantic_table_role_manual == "fact"
            and not str(knowledge_model.semantic_grain_manual or "").strip()
        ):
            knowledge_model.semantic_grain_manual = self._fallback_grain(knowledge_model.table_name)
        db.commit()
        catalog = self._load_active_catalog(db, database_id)
        if catalog is None:
            catalog = self.get_catalog(db, database_id, refresh=True)
        return next((t for t in catalog.tables if t.table_name == table_name), None)

    def patch_catalog_column(
        self,
        db: Session,
        database_id: str,
        table_name: str,
        column_name: str,
        patch: SemanticColumnPatch,
    ) -> SemanticTable | None:
        knowledge_model = (
            db.query(DatabaseKnowledgeColumnModel)
            .filter(
                DatabaseKnowledgeColumnModel.database_id == database_id,
                DatabaseKnowledgeColumnModel.table_name == table_name,
                DatabaseKnowledgeColumnModel.column_name == column_name,
            )
            .first()
        )
        model = (
            db.query(SemanticCatalogColumnModel)
            .join(SemanticCatalogModel, SemanticCatalogColumnModel.catalog_id == SemanticCatalogModel.id)
            .filter(
                SemanticCatalogColumnModel.database_id == database_id,
                SemanticCatalogColumnModel.table_name == table_name,
                SemanticCatalogColumnModel.column_name == column_name,
                SemanticCatalogModel.active.is_(True),
            )
            .first()
        )
        if model is None and knowledge_model is None:
            return None
        if patch.label is not None:
            if model is not None:
                model.label = patch.label
            if knowledge_model is not None:
                knowledge_model.semantic_label_manual = patch.label
        if patch.business_description is not None:
            if model is not None:
                model.business_description = patch.business_description
            if knowledge_model is not None:
                knowledge_model.description_manual = patch.business_description
        if patch.semantic_types is not None:
            if model is not None:
                model.semantic_types = list(patch.semantic_types)
        if patch.analytics_roles is not None:
            if model is not None:
                model.analytics_roles = list(patch.analytics_roles)
        if patch.synonyms is not None:
            if model is not None:
                model.synonyms = list(patch.synonyms)
            if knowledge_model is not None:
                knowledge_model.synonyms = list(patch.synonyms)
        if patch.groupable is not None:
            if model is not None:
                model.groupable = patch.groupable
        if patch.filterable is not None:
            if model is not None:
                model.filterable = patch.filterable
        db.commit()
        catalog = self._load_active_catalog(db, database_id)
        if catalog is None:
            catalog = self.get_catalog(db, database_id, refresh=True)
        return next((t for t in catalog.tables if t.table_name == table_name), None)

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
        semantic_contract = self.semantic_rule_engine.build_contract(
            database_id=database_id,
            facts=self.schema_fact_builder.build(db, database_id),
        )
        semantic_contract.validation_issues = self.semantic_validator.validate(semantic_contract)
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
        schema = self._build_retrieval_schema(
            db,
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
            schema_metadata=schema,
            semantic_contract=semantic_contract,
            dictionary_entries=[entry.model_dump(mode="json") for entry in dictionary_entries],
            table_names=sorted(selected_table_names),
            notes=self._build_notes(selected_tables, selected_join_paths, semantic_contract=semantic_contract),
        )

    def build_schema_context(
        self,
        db: Session,
        database_id: str,
        intent_text: str = "",
        dictionary_entries: list[DictionaryEntryRead] | None = None,
    ) -> SchemaMetadataResponse:
        return SchemaMetadataResponse.model_validate(
            self.build_retrieval_context(db, database_id, intent_text, dictionary_entries).schema_metadata
        )

    def resolve_intent_terms(
        self,
        intent: IntentPayload,
        catalog: SemanticCatalog | None,
        dictionary_entries: list[DictionaryEntryRead] | None = None,
    ) -> SemanticIntentResolution:
        resolution = SemanticIntentResolution()
        if catalog is None:
            return resolution

        dictionary_entries = dictionary_entries or []
        term_index = self._semantic_term_index(catalog, dictionary_entries)

        metric_candidate = self._resolve_term(intent.metric, "metric", term_index)
        if metric_candidate is not None:
            if metric_candidate.resolved:
                resolution.resolved_terms.append(metric_candidate)
            else:
                resolution.unresolved_terms.append(metric_candidate)

        for dimension in intent.dimensions:
            dimension_candidate = self._resolve_term(dimension, "dimension", term_index)
            if dimension_candidate.resolved:
                resolution.resolved_terms.append(dimension_candidate)
            else:
                resolution.unresolved_terms.append(dimension_candidate)

        for filter_item in intent.filters:
            filter_candidate = self._resolve_term(filter_item.field, "filter", term_index)
            if filter_candidate.resolved:
                resolution.resolved_terms.append(filter_candidate)
            else:
                resolution.unresolved_terms.append(filter_candidate)

        resolution.requires_clarification = bool(resolution.unresolved_terms)
        if resolution.requires_clarification:
            resolution.notes.append("Semantic catalog could not confidently resolve one or more business terms.")
        return resolution

    def find_relationships(
        self,
        catalog: SemanticCatalog | None,
        from_term: str,
        to_term: str,
    ) -> list[SemanticRelationship]:
        if catalog is None:
            return []
        from_tokens = set(self._tokenize(from_term))
        to_tokens = set(self._tokenize(to_term))
        matches: list[SemanticRelationship] = []
        for relationship in catalog.relationships:
            left_haystack = " ".join(
                [
                    relationship.from_table,
                    relationship.from_column,
                    relationship.business_meaning,
                    relationship.description or "",
                ]
            ).lower()
            right_haystack = " ".join(
                [
                    relationship.to_table,
                    relationship.to_column,
                    relationship.business_meaning,
                    relationship.description or "",
                ]
            ).lower()
            if (all(token in left_haystack for token in from_tokens) and all(token in right_haystack for token in to_tokens)) or (
                all(token in left_haystack for token in to_tokens) and all(token in right_haystack for token in from_tokens)
            ):
                matches.append(relationship)
        return matches

    def _semantic_term_index(
        self,
        catalog: SemanticCatalog,
        dictionary_entries: list[DictionaryEntryRead],
    ) -> dict[str, list[SemanticTermCandidate]]:
        index: dict[str, list[SemanticTermCandidate]] = defaultdict(list)

        def add(raw_term: str | None, candidate: SemanticTermCandidate) -> None:
            normalized = str(raw_term or "").strip().lower()
            if not normalized:
                return
            bucket = index.setdefault(normalized, [])
            if not any(
                existing.kind == candidate.kind
                and existing.match == candidate.match
                and existing.source == candidate.source
                for existing in bucket
            ):
                bucket.append(candidate)

        for table in catalog.tables:
            for term in [table.table_name, table.label, *table.synonyms]:
                add(
                    term,
                    SemanticTermCandidate(
                        term=str(term),
                        kind="table",
                        match=table.table_name,
                        source="semantic_catalog",
                        confidence=0.9,
                        note=table.business_description or None,
                    ),
                )
            for term in table.important_metrics:
                metric_name, expression = self._split_metric_definition(str(term))
                add(
                    metric_name,
                    SemanticTermCandidate(
                        term=metric_name,
                        kind="metric",
                        match=expression or table.table_name,
                        source="semantic_catalog",
                        confidence=0.88,
                        note=table.business_description or None,
                    ),
                )
            for term in table.important_dimensions:
                add(
                    term,
                    SemanticTermCandidate(
                        term=str(term),
                        kind="dimension",
                        match=table.table_name,
                        source="semantic_catalog",
                        confidence=0.88,
                        note=table.business_description or None,
                    ),
                )
            for column in table.columns:
                base_note = column.business_description or table.business_description or None
                column_terms = [
                    column.column_name,
                    column.label,
                    *column.synonyms,
                    *[str(value) for value in column.example_values[:3]],
                ]
                for term in column_terms:
                    kind = "metric" if "metric" in column.semantic_types or "primary_metric" in column.analytics_roles else "dimension"
                    if kind == "dimension" and "default_filter" in column.analytics_roles:
                        kind = "filter"
                    add(
                        str(term),
                        SemanticTermCandidate(
                            term=str(term),
                            kind=kind,
                            match=f"{table.table_name}.{column.column_name}",
                            source="semantic_catalog",
                            confidence=0.92,
                            note=base_note,
                        ),
                    )

        for entry in dictionary_entries:
            mapped = entry.mapped_expression or entry.term
            add(
                entry.term,
                SemanticTermCandidate(
                    term=entry.term,
                    kind="term",
                    match=mapped,
                    source="dictionary",
                    confidence=0.75,
                    note=entry.description or None,
                ),
            )
            for synonym in entry.synonyms:
                add(
                    str(synonym),
                    SemanticTermCandidate(
                        term=str(synonym),
                        kind="term",
                        match=mapped,
                        source="dictionary",
                        confidence=0.7,
                        note=entry.description or None,
                    ),
                )

        return index

    def _resolve_term(
        self,
        term: str | None,
        kind: str,
        term_index: dict[str, list[SemanticTermCandidate]],
    ) -> SemanticTermResolutionItem | None:
        normalized = str(term or "").strip().lower()
        if not normalized:
            return None

        if kind == "dimension" and normalized in self.TEMPORAL_DIMENSION_TERMS:
            return SemanticTermResolutionItem(
                term=str(term),
                kind=kind,
                resolved=True,
                match=normalized,
                source="schema",
                confidence=0.95,
                note="Temporal granularity is treated as an inherently grounded dimension.",
            )

        direct_matches = list(term_index.get(normalized, []))
        preferred_matches = [item for item in direct_matches if item.kind in {kind, "term"}]
        if preferred_matches:
            best = preferred_matches[0]
            return SemanticTermResolutionItem(
                term=str(term),
                kind=kind,
                resolved=True,
                match=best.match,
                source=best.source,
                confidence=best.confidence,
                candidates=preferred_matches[:5],
                note=best.note,
            )

        token_matches: list[SemanticTermCandidate] = []
        for token in self._tokenize(normalized):
            token_matches.extend(term_index.get(token, []))

        deduped: list[SemanticTermCandidate] = []
        seen: set[tuple[str | None, str, str]] = set()
        for candidate in token_matches:
            key = (candidate.match, candidate.kind, candidate.source)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(candidate)

        return SemanticTermResolutionItem(
            term=str(term),
            kind=kind,
            resolved=False,
            question=f"Уточните, что означает «{term}».",
            candidates=deduped[:5],
            note="Term is not grounded in the semantic catalog.",
        )

    def _build_retrieval_schema(
        self,
        db: Session,
        database_id: str,
        dialect: str,
        tables: list[SemanticTable],
        join_paths: list[SemanticJoinPath],
        relationship_graph: list[RelationshipGraphEdge],
    ) -> SchemaMetadataResponse:
        selected_table_names = {table.table_name for table in tables}
        try:
            from app.services.schema_context_provider import SchemaContextProvider

            base_schema = SchemaContextProvider().get_schema_for_llm(db, database_id)
            filtered_tables = [
                table for table in base_schema.tables
                if table.name in selected_table_names
            ]
            filtered_relationships = [
                relationship for relationship in base_schema.relationships
                if relationship.from_table in selected_table_names and relationship.to_table in selected_table_names
            ]
            filtered_graph = [
                edge for edge in base_schema.relationship_graph
                if edge.from_table in selected_table_names and edge.to_table in selected_table_names
            ]
            if filtered_tables:
                return SchemaMetadataResponse(
                    database_id=base_schema.database_id,
                    dialect=base_schema.dialect,
                    tables=filtered_tables,
                    relationships=filtered_relationships,
                    relationship_graph=filtered_graph or relationship_graph,
                )
        except Exception:
            pass
        return self._catalog_to_schema(
            database_id,
            dialect,
            tables,
            join_paths,
            relationship_graph,
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

    def _merge_descriptions(
        self,
        catalog: SemanticCatalog,
        *,
        table_descriptions: list[SemanticTableDescription],
        relationship_descriptions: list[SemanticRelationshipDescription],
        column_descriptions: list[SemanticColumnDescription],
    ) -> dict[str, dict[str, str]]:
        merged: dict[str, dict[str, str]] = {
            "tables": {},
            "relationships": {},
            "columns": {},
        }
        for table in catalog.tables:
            merged["tables"][table.table_name] = table.business_description
            for column in table.columns:
                merged["columns"][f"{table.table_name}.{column.column_name}"] = column.business_description
        for relationship in catalog.relationships:
            key = self._relationship_key(
                relationship.from_table,
                relationship.from_column,
                relationship.to_table,
                relationship.to_column,
            )
            merged["relationships"][key] = relationship.business_meaning

        for item in table_descriptions:
            merged["tables"][item.table_name.strip()] = item.business_description.strip()
        for item in relationship_descriptions:
            merged["relationships"][
                self._relationship_key(
                    item.from_table,
                    item.from_column,
                    item.to_table,
                    item.to_column,
                )
            ] = item.business_meaning.strip()
        for item in column_descriptions:
            merged["columns"][f"{item.table_name.strip()}.{item.column_name.strip()}"] = item.business_description.strip()
        return merged

    def _apply_manual_descriptions(
        self,
        catalog: SemanticCatalog,
        overrides: dict[str, dict[str, str]],
    ) -> SemanticCatalog:
        updated_tables: list[SemanticTable] = []
        for table in catalog.tables:
            updated_columns = []
            for column in table.columns:
                key = f"{table.table_name}.{column.column_name}"
                updated_columns.append(
                    column.model_copy(
                        update={
                            "business_description": overrides["columns"].get(key, column.business_description),
                        }
                    )
                )
            updated_relationships = []
            for relationship in table.relationships:
                key = self._relationship_key(
                    relationship.from_table,
                    relationship.from_column,
                    relationship.to_table,
                    relationship.to_column,
                )
                updated_relationships.append(
                    relationship.model_copy(
                        update={
                            "business_meaning": overrides["relationships"].get(key, relationship.business_meaning),
                        }
                    )
                )
            updated_tables.append(
                table.model_copy(
                    update={
                        "business_description": overrides["tables"].get(table.table_name, table.business_description),
                        "columns": updated_columns,
                        "relationships": updated_relationships,
                    }
                )
            )

        updated_relationships = []
        for relationship in catalog.relationships:
            key = self._relationship_key(
                relationship.from_table,
                relationship.from_column,
                relationship.to_table,
                relationship.to_column,
            )
            updated_relationships.append(
                relationship.model_copy(
                    update={
                        "business_meaning": overrides["relationships"].get(key, relationship.business_meaning),
                    }
                )
            )

        return catalog.model_copy(
            update={
                "tables": updated_tables,
                "relationships": updated_relationships,
            }
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

    def _relationship_key(self, from_table: str, from_column: str, to_table: str, to_column: str) -> str:
        return f"{from_table}.{from_column}->{to_table}.{to_column}"

    def _catalog_notes(
        self,
        catalog: SemanticCatalog,
        database_description: str | None = None,
    ) -> list[str]:
        notes = [
            f"tables={len(catalog.tables)}",
            f"relationships={len(catalog.relationships)}",
            f"join_paths={len(catalog.join_paths)}",
            f"graph_edges={len(catalog.relationship_graph)}",
        ]
        if database_description and database_description.strip():
            notes.append(f"database_description={database_description.strip()}")
        if self.llm_service.configured:
            notes.append("enriched_with_llm")
        return notes

    def _apply_llm_enrichment(
        self,
        tables: list[SemanticTable],
        relationship_graph: list[RelationshipGraphEdge],
        database_description: str | None = None,
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
            enrichment = self.llm_service.enrich_semantic_table(
                table,
                relationships,
                join_paths,
                graph_edges,
                database_description=database_description,
            )
            if enrichment is None:
                enriched_tables.append(self._ensure_table_semantics(table))
                continue
            merged = self._ensure_table_semantics(self._merge_table_enrichment(table, enrichment))
            enriched_tables.append(merged)
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
            candidate_label = self._clean_enriched_text(column_enrichment.label, column.column_name, table.table_name)
            if candidate_label:
                column.label = candidate_label
            candidate_desc = self._clean_enriched_text(column_enrichment.business_description, column.column_name, table.table_name)
            if candidate_desc:
                column.business_description = candidate_desc
            if column_enrichment.semantic_types:
                column.semantic_types = sorted({*column.semantic_types, *column_enrichment.semantic_types})
            if column_enrichment.analytics_roles:
                column.analytics_roles = sorted({*column.analytics_roles, *column_enrichment.analytics_roles})
            if column_enrichment.synonyms:
                column.synonyms = sorted({*column.synonyms, *column_enrichment.synonyms})

        update_payload: dict[str, Any] = {}
        candidate_table_label = self._clean_enriched_text(enrichment.label, table.table_name, table.table_name)
        if candidate_table_label:
            update_payload["label"] = candidate_table_label
        candidate_table_desc = self._clean_enriched_text(enrichment.business_description, table.table_name, table.table_name)
        if candidate_table_desc:
            update_payload["business_description"] = candidate_table_desc
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
            update_payload["important_metrics"] = self._normalize_important_metrics(
                [*table.important_metrics, *enrichment.important_metrics],
                table.columns,
            )
        if enrichment.important_dimensions:
            update_payload["important_dimensions"] = sorted({*table.important_dimensions, *enrichment.important_dimensions})
        return table.model_copy(update=update_payload)

    def _ensure_table_semantics(self, table: SemanticTable) -> SemanticTable:
        update_payload: dict[str, Any] = {
            "important_metrics": self._normalize_important_metrics(table.important_metrics, table.columns)
        }
        if table.table_role == "fact" and not str(table.grain or "").strip():
            update_payload["grain"] = self._fallback_grain(table.table_name)
        if table.main_date_column and not any(column.column_name == table.main_date_column for column in table.columns):
            update_payload["main_date_column"] = self._pick_main_date_column(table.columns)
        return table.model_copy(update=update_payload)

    def _fallback_grain(self, table_name: str) -> str:
        return f"one row = one {self._humanize(table_name, plural=False).lower()}"

    def _normalize_important_metrics(
        self,
        metrics: list[str],
        columns: list[SemanticColumn],
    ) -> list[str]:
        normalized: list[str] = []
        column_map = {column.column_name.lower(): column for column in columns}
        for raw_metric in metrics:
            candidate = str(raw_metric or "").strip()
            if not candidate:
                continue
            metric_name, expression = self._split_metric_definition(candidate)
            if expression:
                normalized.append(f"{metric_name}: {expression}")
                continue
            column = column_map.get(candidate.lower())
            if column is None:
                normalized.append(candidate)
                continue
            inferred = self._metric_definition_from_column(column)
            if inferred:
                normalized.append(inferred)
        return sorted(dict.fromkeys(normalized))

    def _split_metric_definition(self, value: str) -> tuple[str, str | None]:
        if ":" not in value:
            return value.strip(), None
        name, expression = value.split(":", 1)
        normalized_name = str(name or "").strip()
        normalized_expression = str(expression or "").strip()
        if not normalized_name or not normalized_expression:
            return value.strip(), None
        return normalized_name, normalized_expression

    def _infer_important_metrics(
        self,
        table_name: str,
        columns: list[SemanticColumn],
        table_role: TableRole,
    ) -> list[str]:
        metrics: list[str] = []
        if table_role in {"fact", "event", "snapshot"}:
            metrics.append("row_count: COUNT(*)")
        for column in columns:
            if "primary_metric" not in column.analytics_roles and "metric" not in column.semantic_types:
                continue
            metric_definition = self._metric_definition_from_column(column)
            if metric_definition:
                metrics.append(metric_definition)
        if not metrics and table_role == "fact":
            metrics.append(f"{table_name}_count: COUNT(*)")
        return sorted(dict.fromkeys(metrics))[:6]

    def _metric_definition_from_column(self, column: SemanticColumn) -> str | None:
        aggregation = self._metric_aggregation(column)
        if aggregation is None:
            return None
        metric_name = self._metric_name(column, aggregation)
        return f"{metric_name}: {aggregation}({column.column_name})"

    def _metric_aggregation(self, column: SemanticColumn) -> str | None:
        if not column.aggregation:
            return None
        if "currency" in column.semantic_types or column.value_type in {"currency", "numeric"}:
            return "SUM"
        if "ratio" in column.semantic_types or column.value_type == "ratio":
            return "AVG"
        if "duration" in column.semantic_types or column.value_type == "duration":
            return "AVG"
        if any(name in column.column_name.lower() for name in _COUNT_NAME_HINTS):
            return "COUNT"
        if "sum" in column.aggregation:
            return "SUM"
        if "avg" in column.aggregation:
            return "AVG"
        return None

    def _metric_name(self, column: SemanticColumn, aggregation: str) -> str:
        column_name = column.column_name.lower()
        if aggregation == "SUM":
            return f"total_{column_name}"
        if aggregation == "AVG":
            return f"avg_{column_name}"
        if aggregation == "COUNT":
            return f"{column_name}_count"
        return column_name

    _GENERIC_TEXTS = {"no description", "n/a", "na", "unknown"}

    def _clean_enriched_text(self, value: str | None, subject: str, table_name: str) -> str | None:
        if value is None:
            return None
        candidate = value.strip()
        if not candidate:
            return None
        lowered = re.sub(r"\s+", " ", candidate.lower())
        subject_norm = re.sub(r"\s+", " ", subject.lower()).strip()
        table_norm = re.sub(r"\s+", " ", table_name.lower()).strip()
        if lowered in self._GENERIC_TEXTS:
            return None
        if subject_norm and lowered == subject_norm:
            return None
        if table_norm and lowered == table_norm:
            return None
        templated_variants = {
            f"physical table {table_norm}",
            f"table {table_norm}",
            f"таблица {table_norm}",
            f"column {subject_norm} in {table_norm}",
            f"column {subject_norm} of {table_norm}",
            f"field {subject_norm} in {table_norm}",
            f"поле {subject_norm} в {table_norm}",
            f"колонка {subject_norm} в {table_norm}",
        }
        if lowered in templated_variants:
            return None
        if lowered.startswith(("column ", "field ", "поле ", "колонка ")) and table_norm and table_norm in lowered and len(candidate) < 80:
            return None
        if len(candidate) < 4:
            return None
        return candidate

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
        language_hint: str = "unknown",
    ) -> SemanticTable:
        columns_meta = self._safe_get_columns(inspector, schema_name, table_name)
        pk_constraint = self._safe_get_pk(inspector, schema_name, table_name)
        table_comment = self._safe_get_table_comment(inspector, schema_name, table_name)
        indexes = self._safe_get_indexes(inspector, schema_name, table_name)
        sample_rows = self._sample_rows(engine, schema_name, table_name)
        relationship_rows = self._safe_get_foreign_keys(inspector, schema_name, table_name)

        columns: list[SemanticColumn] = []
        relationships: list[SemanticRelationship] = []
        physical_columns = {
            column.column_name: column
            for column in getattr(physical, "columns", []) or []
            if getattr(column, "status", "active") == "active"
        }
        hidden_column_names = {
            column_name
            for column_name, column in physical_columns.items()
            if bool(getattr(column, "hidden_for_llm", False))
        }
        physical_relationships = {
            self._relationship_key(
                relationship.from_table_name,
                relationship.from_column_name,
                relationship.to_table_name,
                relationship.to_column_name,
            ): relationship
            for relationship in getattr(physical, "_prefetched_relationships", []) or []
        }
        fk_lookup = {
            row["constrained_columns"][0]: row
            for row in relationship_rows
            if row.get("constrained_columns") and row.get("referred_table")
        }
        primary_key = [
            str(name)
            for name in (pk_constraint.get("constrained_columns") or [])
            if name and str(name) not in hidden_column_names
        ]

        for ordinal, column in enumerate(columns_meta, start=1):
            column_name = str(column.get("name"))
            if column_name in hidden_column_names:
                continue
            foreign_key = fk_lookup.get(column_name)
            physical_column = physical_columns.get(column_name)
            profile = self._profile_column(column_name, sample_rows)
            if physical_column is not None:
                profile = profile.model_copy(
                    update={
                        "distinct_count": physical_column.distinct_count or profile.distinct_count,
                        "null_ratio": (
                            physical_column.null_ratio
                            if physical_column.null_ratio is not None
                            else profile.null_ratio
                        ),
                        "min_value": physical_column.min_value or profile.min_value,
                        "max_value": physical_column.max_value or profile.max_value,
                        "top_values": list(physical_column.sample_values or []) or profile.top_values,
                    }
                )
            semantic_types, analytics_roles, value_type, aggregation, filterable, groupable, sortable = self._infer_column_semantics(
                table_name=table_name,
                column_name=column_name,
                data_type=str(column.get("type")),
                profile=profile,
                is_pk=column_name in primary_key,
                foreign_key=foreign_key,
            )
            label = (
                str(physical_column.semantic_label_manual).strip()
                if physical_column is not None and str(physical_column.semantic_label_manual or "").strip()
                else self._humanize(column_name)
            )
            business_description = (
                str(physical_column.description_manual).strip()
                if physical_column is not None and str(physical_column.description_manual or "").strip()
                else self._default_column_description(table_name, column_name, language_hint=language_hint)
            )
            if column_name in primary_key:
                business_description = self._primary_key_description(table_name, language_hint=language_hint)
            if foreign_key:
                business_description = self._foreign_key_description(foreign_key.get("referred_table"), language_hint=language_hint)
            if physical_column is not None and str(physical_column.description_manual or "").strip():
                business_description = str(physical_column.description_manual).strip()

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
                    synonyms=(
                        list(physical_column.synonyms or [])
                        if physical_column is not None and list(physical_column.synonyms or [])
                        else self._column_synonyms(table_name, column_name, label)
                    ),
                    example_values=(
                        list(physical_column.sample_values or [])[:5]
                        if physical_column is not None and list(physical_column.sample_values or [])
                        else profile.top_values[:5]
                    ),
                    data_type=(
                        physical_column.data_type
                        if physical_column is not None and physical_column.data_type
                        else str(column.get("type"))
                    ),
                    nullable=(
                        bool(physical_column.is_nullable)
                        if physical_column is not None
                        else bool(column.get("nullable", True))
                    ),
                    default_value=(
                        physical_column.default_value
                        if physical_column is not None
                        else self._stringify(column.get("default"))
                    ),
                    max_length=self._max_length_from_type(
                        physical_column.data_type if physical_column is not None and physical_column.data_type else str(column.get("type"))
                    ),
                    ordinal_position=(
                        int(physical_column.ordinal_position)
                        if physical_column is not None
                        else ordinal
                    ),
                    is_pk=column_name in primary_key,
                    is_fk=foreign_key is not None,
                    referenced_table=str(foreign_key.get("referred_table")) if foreign_key else None,
                    referenced_column=str((foreign_key.get("referred_columns") or [None])[0]) if foreign_key else None,
                    comment=self._stringify(column.get("comment")),
                    profile=profile,
                )
            )

            if foreign_key:
                relationship = self._build_relationship(
                    table_name=table_name,
                    column_name=column_name,
                    foreign_key=foreign_key,
                )
                physical_relationship = physical_relationships.get(
                    self._relationship_key(
                        relationship.from_table,
                        relationship.from_column,
                        relationship.to_table,
                        relationship.to_column,
                    )
                )
                if physical_relationship is not None:
                    relationship = relationship.model_copy(
                        update={
                            "business_meaning": (
                                str(physical_relationship.description_manual).strip()
                                if str(physical_relationship.description_manual or "").strip()
                                else relationship.business_meaning
                            ),
                            "confidence": float(physical_relationship.confidence or relationship.confidence),
                        }
                    )
                relationships.append(relationship)

        # Also build relationships from manually-defined records (e.g., CSV/DuckDB without FK constraints)
        built_keys = {
            self._relationship_key(r.from_table, r.from_column, r.to_table, r.to_column)
            for r in relationships
        }
        for rel_key, physical_rel in physical_relationships.items():
            if rel_key not in built_keys and physical_rel.from_table_name == table_name:
                relationships.append(
                    SemanticRelationship(
                        from_table=physical_rel.from_table_name,
                        from_column=physical_rel.from_column_name,
                        to_table=physical_rel.to_table_name,
                        to_column=physical_rel.to_column_name,
                        relationship_type="many-to-one",
                        join_type="inner",
                        business_meaning=str(physical_rel.description_manual or ""),
                        join_priority="medium",
                        confidence=float(physical_rel.confidence or 0.9),
                    )
                )

        row_count = physical.row_count if physical is not None and physical.row_count is not None else self._safe_row_count(engine, schema_name, table_name)
        inferred_table_role = self._infer_table_role(table_name, columns, relationships, row_count)
        table_role = (
            physical.semantic_table_role_manual
            if physical is not None and str(physical.semantic_table_role_manual or "").strip()
            else inferred_table_role
        )
        main_date_column = (
            physical.semantic_main_date_column_manual
            if physical is not None and str(physical.semantic_main_date_column_manual or "").strip()
            else self._pick_main_date_column(columns)
        )
        main_entity = (
            physical.semantic_main_entity_manual
            if physical is not None and str(physical.semantic_main_entity_manual or "").strip()
            else self._humanize(table_name)
        )
        important_metrics = (
            list(physical.semantic_important_metrics or [])
            if physical is not None and list(physical.semantic_important_metrics or [])
            else self._infer_important_metrics(table_name, columns, table_role)
        )
        important_dimensions = [
            column.column_name
            for column in columns
            if any(role in column.analytics_roles for role in ("default_group_by", "default_filter", "display_name", "time_axis"))
        ]
        if physical is not None and list(physical.semantic_important_dimensions or []):
            important_dimensions = list(physical.semantic_important_dimensions or [])

        return SemanticTable(
            schema_name=schema_name,
            table_name=table_name,
            label=(
                str(physical.semantic_label_manual).strip()
                if physical is not None and str(physical.semantic_label_manual or "").strip()
                else self._humanize(table_name)
            ),
            business_description=(
                str(physical.description_manual).strip()
                if physical is not None and str(physical.description_manual or "").strip()
                else self._default_table_description(table_name, language_hint=language_hint)
            ),
            table_role=table_role,
            grain=(
                physical.semantic_grain_manual
                if physical is not None and str(physical.semantic_grain_manual or "").strip()
                else self._infer_grain(table_name, columns)
            ),
            main_date_column=main_date_column,
            main_entity=main_entity,
            synonyms=(
                list(physical.semantic_synonyms or [])
                if physical is not None and list(physical.semantic_synonyms or [])
                else self._table_synonyms(table_name)
            ),
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
        numeric_mean = self._finite_float(round(mean(numeric_values), 4)) if numeric_values else None
        numeric_min = self._finite_float(round(min(numeric_values), 4)) if numeric_values else None
        numeric_max = self._finite_float(round(max(numeric_values), 4)) if numeric_values else None
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

    def _tokenize(self, text: str) -> list[str]:
        return [token for token in text.lower().split() if token]

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
                    description=table.business_description,
                    columns=[
                        ColumnMetadata(
                            name=column.column_name,
                            type=self._resolve_column_type(column),
                            min_value=column.profile.min_value,
                            max_value=column.profile.max_value,
                            description=column.business_description,
                        )
                        for column in table.columns
                    ],
                )
                for table in tables
            ],
            relationships=relationships,
            relationship_graph=relationship_graph,
        )

    _VALUE_TYPE_TO_SQL: dict[str, str] = {
        "datetime": "timestamp",
        "date": "date",
        "currency": "numeric",
        "numeric": "numeric",
        "ratio": "float",
        "duration": "integer",
        "identifier": "varchar",
        "status": "varchar",
        "boolean": "boolean",
        "text": "text",
    }

    def _resolve_column_type(self, column: "SemanticColumn") -> str:
        if column.data_type:
            return column.data_type
        if column.value_type:
            return self._VALUE_TYPE_TO_SQL.get(column.value_type, column.value_type)
        return ""

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
        entries = [
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
        for index, metric in enumerate(table.important_metrics, start=1):
            metric_name, expression = self._split_metric_definition(metric)
            if not expression:
                continue
            entries.append(
                DictionaryEntryRead.model_validate(
                    {
                        "id": f"{table.schema_name}.{table.table_name}.important_metric.{index}",
                        "term": metric_name,
                        "synonyms": [metric_name.replace("_", " "), table.label],
                        "mapped_expression": expression,
                        "description": table.business_description,
                        "object_type": "metric",
                        "table_name": table.table_name,
                        "column_name": None,
                        "source_database": None,
                    }
                )
            )
        return entries

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

    def _build_notes(
        self,
        tables: list[SemanticTable],
        join_paths: list[SemanticJoinPath],
        *,
        semantic_contract=None,
    ) -> list[str]:
        notes: list[str] = []
        for table in tables:
            parts = [
                f"{table.table_name}: role={table.table_role}",
                f"rows~{table.row_count_estimate}",
            ]
            if table.grain:
                parts.append(f"grain={table.grain}")
            if table.main_date_column:
                parts.append(f"main_date={table.main_date_column}")
            if table.important_metrics:
                parts.append(f"metrics={', '.join(table.important_metrics[:2])}")
            notes.append(", ".join(parts))
        if join_paths:
            notes.append(f"join_paths={len(join_paths)}")
        if semantic_contract is not None:
            notes.append(
                "schema_truth_tables=" + ", ".join(sorted(semantic_contract.table_names))
            )
            for issue in semantic_contract.validation_issues[:5]:
                suffix = f" ({issue.table}.{issue.column})" if issue.table and issue.column else f" ({issue.table})" if issue.table else ""
                notes.append(f"semantic_validation:{issue.code}{suffix}")
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

    def _default_table_description(self, table_name: str, language_hint: str = "unknown") -> str:
        if language_hint == "ru":
            return f"Физическая таблица {table_name.replace('_', ' ')}."
        return f"Physical table {table_name.replace('_', ' ')}."

    def _default_column_description(self, table_name: str, column_name: str, language_hint: str = "unknown") -> str:
        if language_hint == "ru":
            return f"Колонка {column_name} в таблице {table_name}."
        return f"Column {column_name} in {table_name}."

    def _primary_key_description(self, table_name: str, language_hint: str = "unknown") -> str:
        if language_hint == "ru":
            return f"Первичный ключ таблицы {table_name}."
        return f"Primary key for {table_name}."

    def _foreign_key_description(self, referred_table: Any | None, language_hint: str = "unknown") -> str:
        target = str(referred_table) if referred_table else "referenced table"
        if language_hint == "ru":
            return f"Внешний ключ на таблицу {target}."
        return f"Foreign key to {target}."

    def _detect_language(self, *texts: str | None) -> str:
        joined = " ".join(text for text in texts if text)
        if not joined:
            return "unknown"
        cyrillic = sum(1 for ch in joined if "\u0400" <= ch <= "\u04FF")
        latin = sum(1 for ch in joined if "a" <= ch.lower() <= "z")
        if cyrillic > latin:
            return "ru"
        if latin > 0:
            return "en"
        return "unknown"

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
                candidate = float(value)
                if math.isfinite(candidate):
                    numeric.append(candidate)
                continue
            except Exception:
                pass
            try:
                candidate = float(str(value).replace(",", "."))
                if math.isfinite(candidate):
                    numeric.append(candidate)
            except Exception:
                continue
        return numeric

    def _finite_float(self, value: float | None) -> float | None:
        if value is None or not math.isfinite(value):
            return None
        return value

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
