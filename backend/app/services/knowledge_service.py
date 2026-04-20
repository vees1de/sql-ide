from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import MetaData, Table, and_, func, inspect as sa_inspect, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import (
    DatabaseConnectionModel,
    DatabaseKnowledgeColumnModel,
    DatabaseKnowledgeRelationshipModel,
    DatabaseKnowledgeScanRunModel,
    DatabaseKnowledgeTableModel,
)
from app.db.session import analytics_engine
from app.schemas.knowledge import (
    ERDEdge,
    ERDGraphResponse,
    ERDNode,
    KnowledgeColumnRead,
    KnowledgeColumnUpdate,
    KnowledgeRelationshipRead,
    KnowledgeRelationshipUpdate,
    KnowledgeScanRunRead,
    KnowledgeSummaryResponse,
    KnowledgeTableRead,
    KnowledgeTableUpdate,
)
from app.services.database_connection_utils import DatabaseConnectionPayload, create_connection_engine
from app.services.dictionary_service import DictionaryService


SYSTEM_SCHEMAS = {
    "information_schema",
    "pg_catalog",
    "pg_toast",
    "mysql",
    "performance_schema",
    "sys",
}
ROW_COUNT_LIMIT = 25
SAMPLE_ROW_LIMIT = 5
SAMPLE_VALUE_LIMIT = 5


@dataclass(frozen=True)
class _ResolvedTarget:
    database_id: str
    database_label: str
    dialect: str
    allowed_tables: set[str] | None
    engine: Any
    dispose_on_close: bool = False


class KnowledgeService:
    def __init__(self) -> None:
        self.dictionary_service = DictionaryService()

    def scan_database(
        self,
        db: Session,
        database_id: str,
        *,
        scan_type: str = "full",
        sync_dictionary: bool = True,
    ) -> DatabaseKnowledgeScanRunModel:
        target = self._resolve_target(db, database_id)
        scan = DatabaseKnowledgeScanRunModel(
            database_id=target.database_id,
            database_label=target.database_label,
            dialect=target.dialect,
            scan_type=scan_type,
            status="running",
            stage="introspection",
            summary={},
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)

        introspected_tables: list[dict[str, Any]] = []
        introspected_relationships: list[dict[str, Any]] = []
        dictionary_payload: list[dict[str, object]] = []

        try:
            inspector = sa_inspect(target.engine)
            schemas = self._list_schemas(inspector, target.dialect)

            counted_tables = 0
            for schema_name in schemas:
                for object_type, table_names in (
                    ("table", inspector.get_table_names(schema=schema_name)),
                    ("view", inspector.get_view_names(schema=schema_name)),
                ):
                    for table_name in sorted(table_names):
                        if table_name.startswith("sqlite_"):
                            continue
                        if target.allowed_tables and table_name not in target.allowed_tables:
                            continue

                        column_dicts = inspector.get_columns(table_name, schema=schema_name)
                        column_names = [str(item["name"]) for item in column_dicts]
                        pk_constraint = inspector.get_pk_constraint(table_name, schema=schema_name) or {}
                        primary_key = [
                            str(name)
                            for name in (pk_constraint.get("constrained_columns") or [])
                            if name
                        ]
                        row_count: int | None = None
                        sample_values: dict[str, list[str]] = {}
                        if object_type == "table":
                            if counted_tables < ROW_COUNT_LIMIT:
                                row_count = self._safe_row_count(target.engine, schema_name, table_name)
                                counted_tables += 1
                            sample_values = self._safe_sample_values(
                                target.engine,
                                schema_name,
                                table_name,
                                column_names,
                            )

                        introspected_tables.append(
                            {
                                "schema_name": schema_name,
                                "table_name": table_name,
                                "object_type": object_type,
                                "row_count": row_count,
                                "primary_key": primary_key,
                                "columns": [
                                    {
                                        "name": str(column["name"]),
                                        "type": str(column["type"]),
                                        "nullable": bool(column.get("nullable", True)),
                                        "default": self._stringify_scalar(column.get("default")),
                                        "ordinal_position": index,
                                        "sample_values": sample_values.get(str(column["name"]), []),
                                    }
                                    for index, column in enumerate(column_dicts, start=1)
                                ],
                            }
                        )
                        dictionary_payload.append(
                            {
                                "name": table_name,
                                "columns": [
                                    {"name": str(column["name"]), "type": str(column["type"])}
                                    for column in column_dicts
                                ],
                            }
                        )

                        for foreign_key in inspector.get_foreign_keys(table_name, schema=schema_name):
                            referred_table = foreign_key.get("referred_table")
                            if not referred_table:
                                continue
                            from_columns = [
                                str(column)
                                for column in (foreign_key.get("constrained_columns") or [])
                                if column
                            ]
                            to_columns = [
                                str(column)
                                for column in (foreign_key.get("referred_columns") or [])
                                if column
                            ]
                            referred_schema = str(
                                foreign_key.get("referred_schema")
                                or schema_name
                                or self._default_schema(target.dialect)
                            )
                            for from_column, to_column in zip(from_columns, to_columns):
                                introspected_relationships.append(
                                    {
                                        "from_schema_name": schema_name,
                                        "from_table_name": table_name,
                                        "from_column_name": from_column,
                                        "to_schema_name": referred_schema,
                                        "to_table_name": str(referred_table),
                                        "to_column_name": to_column,
                                        "relation_type": "physical_fk",
                                        "cardinality": "many_to_one",
                                        "confidence": 1.0,
                                    }
                                )

            scan.stage = "persisting"
            db.commit()

            summary = self._persist_snapshot(
                db,
                target.database_id,
                scan.id,
                introspected_tables=introspected_tables,
                introspected_relationships=introspected_relationships,
            )

            scan.stage = "dictionary"
            db.commit()
            dictionary_imported = 0
            if sync_dictionary and dictionary_payload:
                dictionary_imported = self.dictionary_service.import_schema_tables(
                    db,
                    dictionary_payload,
                    database_label=target.database_label,
                )
            summary["dictionary_entries_imported"] = dictionary_imported

            scan.stage = "completed"
            scan.status = "completed"
            scan.summary = summary
            scan.finished_at = datetime.utcnow()
            db.commit()
            db.refresh(scan)
            return scan
        except Exception as exc:  # noqa: BLE001
            scan.status = "failed"
            scan.stage = "failed"
            scan.error_message = str(exc)
            scan.finished_at = datetime.utcnow()
            db.commit()
            db.refresh(scan)
            raise
        finally:
            if target.dispose_on_close:
                target.engine.dispose()

    def list_scan_runs(self, db: Session, database_id: str) -> list[DatabaseKnowledgeScanRunModel]:
        return (
            db.query(DatabaseKnowledgeScanRunModel)
            .filter(DatabaseKnowledgeScanRunModel.database_id == database_id)
            .order_by(DatabaseKnowledgeScanRunModel.started_at.desc())
            .all()
        )

    def get_scan_run(self, db: Session, scan_run_id: str) -> DatabaseKnowledgeScanRunModel | None:
        return (
            db.query(DatabaseKnowledgeScanRunModel)
            .filter(DatabaseKnowledgeScanRunModel.id == scan_run_id)
            .first()
        )

    def get_summary(self, db: Session, database_id: str) -> KnowledgeSummaryResponse:
        target = self._resolve_target(db, database_id)
        try:
            latest_scan = (
                db.query(DatabaseKnowledgeScanRunModel)
                .filter(DatabaseKnowledgeScanRunModel.database_id == database_id)
                .order_by(DatabaseKnowledgeScanRunModel.started_at.desc())
                .first()
            )
            tables = (
                db.query(DatabaseKnowledgeTableModel)
                .filter(
                    DatabaseKnowledgeTableModel.database_id == database_id,
                    DatabaseKnowledgeTableModel.status == "active",
                )
                .order_by(DatabaseKnowledgeTableModel.schema_name.asc(), DatabaseKnowledgeTableModel.table_name.asc())
                .all()
            )
            active_column_count = (
                db.query(DatabaseKnowledgeColumnModel)
                .filter(
                    DatabaseKnowledgeColumnModel.database_id == database_id,
                    DatabaseKnowledgeColumnModel.status == "active",
                )
                .count()
            )
            active_relationship_count = (
                db.query(DatabaseKnowledgeRelationshipModel)
                .filter(
                    DatabaseKnowledgeRelationshipModel.database_id == database_id,
                    DatabaseKnowledgeRelationshipModel.status == "active",
                    DatabaseKnowledgeRelationshipModel.is_disabled.is_(False),
                )
                .count()
            )
            status = latest_scan.status if latest_scan is not None else "not_scanned"
            return KnowledgeSummaryResponse(
                database_id=database_id,
                database_label=target.database_label,
                dialect=target.dialect,
                status=status,
                active_table_count=len(tables),
                active_column_count=active_column_count,
                active_relationship_count=active_relationship_count,
                last_scan=KnowledgeScanRunRead.model_validate(latest_scan) if latest_scan else None,
                tables=[
                    KnowledgeTableRead(
                        id=table.id,
                        database_id=table.database_id,
                        schema_name=table.schema_name,
                        table_name=table.table_name,
                        object_type=table.object_type,
                        status=table.status,
                        column_count=table.column_count,
                        row_count=table.row_count,
                        primary_key=list(table.primary_key or []),
                        description_auto=table.description_auto,
                        description_manual=table.description_manual,
                        business_meaning_auto=table.business_meaning_auto,
                        business_meaning_manual=table.business_meaning_manual,
                        domain_auto=table.domain_auto,
                        domain_manual=table.domain_manual,
                        tags=list(table.tags or []),
                        sensitivity=table.sensitivity,
                        usage_score=table.usage_score,
                    )
                    for table in tables
                ],
            )
        finally:
            if target.dispose_on_close:
                target.engine.dispose()

    def get_table(self, db: Session, table_id: str) -> DatabaseKnowledgeTableModel | None:
        table = (
            db.query(DatabaseKnowledgeTableModel)
            .options(selectinload(DatabaseKnowledgeTableModel.columns))
            .filter(DatabaseKnowledgeTableModel.id == table_id)
            .first()
        )
        if table is None:
            return None
        relationships = (
            db.query(DatabaseKnowledgeRelationshipModel)
            .filter(
                DatabaseKnowledgeRelationshipModel.database_id == table.database_id,
                DatabaseKnowledgeRelationshipModel.status == "active",
                DatabaseKnowledgeRelationshipModel.is_disabled.is_(False),
            )
            .filter(
                or_(
                    and_(
                        DatabaseKnowledgeRelationshipModel.from_schema_name == table.schema_name,
                        DatabaseKnowledgeRelationshipModel.from_table_name == table.table_name,
                    ),
                    and_(
                        DatabaseKnowledgeRelationshipModel.to_schema_name == table.schema_name,
                        DatabaseKnowledgeRelationshipModel.to_table_name == table.table_name,
                    ),
                )
            )
            .order_by(
                DatabaseKnowledgeRelationshipModel.from_table_name.asc(),
                DatabaseKnowledgeRelationshipModel.to_table_name.asc(),
            )
            .all()
        )
        setattr(table, "_prefetched_relationships", relationships)
        return table

    def get_table_by_key(
        self,
        db: Session,
        database_id: str,
        schema_name: str,
        table_name: str,
    ) -> DatabaseKnowledgeTableModel | None:
        table = (
            db.query(DatabaseKnowledgeTableModel)
            .options(selectinload(DatabaseKnowledgeTableModel.columns))
            .filter(
                DatabaseKnowledgeTableModel.database_id == database_id,
                DatabaseKnowledgeTableModel.schema_name == schema_name,
                DatabaseKnowledgeTableModel.table_name == table_name,
            )
            .first()
        )
        if table is None:
            return None
        relationships = (
            db.query(DatabaseKnowledgeRelationshipModel)
            .filter(
                DatabaseKnowledgeRelationshipModel.database_id == table.database_id,
                DatabaseKnowledgeRelationshipModel.status == "active",
                DatabaseKnowledgeRelationshipModel.is_disabled.is_(False),
            )
            .filter(
                or_(
                    and_(
                        DatabaseKnowledgeRelationshipModel.from_schema_name == table.schema_name,
                        DatabaseKnowledgeRelationshipModel.from_table_name == table.table_name,
                    ),
                    and_(
                        DatabaseKnowledgeRelationshipModel.to_schema_name == table.schema_name,
                        DatabaseKnowledgeRelationshipModel.to_table_name == table.table_name,
                    ),
                )
            )
            .order_by(
                DatabaseKnowledgeRelationshipModel.from_table_name.asc(),
                DatabaseKnowledgeRelationshipModel.to_table_name.asc(),
            )
            .all()
        )
        setattr(table, "_prefetched_relationships", relationships)
        return table

    def update_table(
        self,
        db: Session,
        table_id: str,
        payload: KnowledgeTableUpdate,
    ) -> DatabaseKnowledgeTableModel | None:
        table = db.query(DatabaseKnowledgeTableModel).filter(DatabaseKnowledgeTableModel.id == table_id).first()
        if table is None:
            return None
        if payload.description_manual is not None:
            table.description_manual = payload.description_manual
        if payload.business_meaning_manual is not None:
            table.business_meaning_manual = payload.business_meaning_manual
        if payload.domain_manual is not None:
            table.domain_manual = payload.domain_manual
        if payload.tags is not None:
            table.tags = payload.tags
        if payload.sensitivity is not None:
            table.sensitivity = payload.sensitivity
        db.commit()
        db.refresh(table)
        return table

    def update_column(
        self,
        db: Session,
        column_id: str,
        payload: KnowledgeColumnUpdate,
    ) -> DatabaseKnowledgeColumnModel | None:
        column = db.query(DatabaseKnowledgeColumnModel).filter(DatabaseKnowledgeColumnModel.id == column_id).first()
        if column is None:
            return None
        if payload.description_manual is not None:
            column.description_manual = payload.description_manual
        if payload.semantic_label_manual is not None:
            column.semantic_label_manual = payload.semantic_label_manual
        if payload.synonyms is not None:
            column.synonyms = payload.synonyms
        if payload.sensitivity is not None:
            column.sensitivity = payload.sensitivity
        if payload.hidden_for_llm is not None:
            column.hidden_for_llm = payload.hidden_for_llm
        db.commit()
        db.refresh(column)
        return column

    def update_relationship(
        self,
        db: Session,
        relationship_id: str,
        payload: KnowledgeRelationshipUpdate,
    ) -> DatabaseKnowledgeRelationshipModel | None:
        relationship = (
            db.query(DatabaseKnowledgeRelationshipModel)
            .filter(DatabaseKnowledgeRelationshipModel.id == relationship_id)
            .first()
        )
        if relationship is None:
            return None
        if payload.cardinality is not None:
            relationship.cardinality = payload.cardinality
        if payload.confidence is not None:
            relationship.confidence = payload.confidence
        if payload.approved is not None:
            relationship.approved = payload.approved
        if payload.is_disabled is not None:
            relationship.is_disabled = payload.is_disabled
        if payload.description_manual is not None:
            relationship.description_manual = payload.description_manual
        db.commit()
        db.refresh(relationship)
        return relationship

    def build_erd(self, db: Session, database_id: str) -> ERDGraphResponse:
        tables = (
            db.query(DatabaseKnowledgeTableModel)
            .filter(
                DatabaseKnowledgeTableModel.database_id == database_id,
                DatabaseKnowledgeTableModel.status == "active",
            )
            .order_by(DatabaseKnowledgeTableModel.schema_name.asc(), DatabaseKnowledgeTableModel.table_name.asc())
            .all()
        )
        relationships = (
            db.query(DatabaseKnowledgeRelationshipModel)
            .filter(
                DatabaseKnowledgeRelationshipModel.database_id == database_id,
                DatabaseKnowledgeRelationshipModel.status == "active",
                DatabaseKnowledgeRelationshipModel.is_disabled.is_(False),
            )
            .order_by(
                DatabaseKnowledgeRelationshipModel.from_table_name.asc(),
                DatabaseKnowledgeRelationshipModel.to_table_name.asc(),
            )
            .all()
        )
        table_map = {(table.schema_name, table.table_name): table for table in tables}
        nodes = [
            ERDNode(
                id=table.id,
                label=f"{table.schema_name}.{table.table_name}",
                schema_name=table.schema_name,
                table_name=table.table_name,
                column_count=table.column_count,
                row_count=table.row_count,
                tags=list(table.tags or []),
            )
            for table in tables
        ]
        edges: list[ERDEdge] = []
        for relationship in relationships:
            source = table_map.get((relationship.from_schema_name, relationship.from_table_name))
            target = table_map.get((relationship.to_schema_name, relationship.to_table_name))
            if source is None or target is None:
                continue
            edges.append(
                ERDEdge(
                    id=relationship.id,
                    source=source.id,
                    target=target.id,
                    source_label=f"{relationship.from_table_name}.{relationship.from_column_name}",
                    target_label=f"{relationship.to_table_name}.{relationship.to_column_name}",
                    relation_type=relationship.relation_type,
                    confidence=relationship.confidence,
                    cardinality=relationship.cardinality,
                )
            )
        return ERDGraphResponse(database_id=database_id, nodes=nodes, edges=edges)

    def serialize_table(self, table: DatabaseKnowledgeTableModel) -> KnowledgeTableRead:
        relationships = getattr(table, "_prefetched_relationships", [])
        return KnowledgeTableRead(
            id=table.id,
            database_id=table.database_id,
            schema_name=table.schema_name,
            table_name=table.table_name,
            object_type=table.object_type,
            status=table.status,
            column_count=table.column_count,
            row_count=table.row_count,
            primary_key=list(table.primary_key or []),
            description_auto=table.description_auto,
            description_manual=table.description_manual,
            business_meaning_auto=table.business_meaning_auto,
            business_meaning_manual=table.business_meaning_manual,
            domain_auto=table.domain_auto,
            domain_manual=table.domain_manual,
            tags=list(table.tags or []),
            sensitivity=table.sensitivity,
            usage_score=table.usage_score,
            columns=[
                KnowledgeColumnRead(
                    id=column.id,
                    database_id=column.database_id,
                    table_id=column.table_id,
                    schema_name=column.schema_name,
                    table_name=column.table_name,
                    column_name=column.column_name,
                    data_type=column.data_type,
                    ordinal_position=column.ordinal_position,
                    is_nullable=column.is_nullable,
                    default_value=column.default_value,
                    status=column.status,
                    distinct_count=column.distinct_count,
                    null_ratio=column.null_ratio,
                    min_value=column.min_value,
                    max_value=column.max_value,
                    sample_values=list(column.sample_values or []),
                    semantic_label_auto=column.semantic_label_auto,
                    semantic_label_manual=column.semantic_label_manual,
                    description_auto=column.description_auto,
                    description_manual=column.description_manual,
                    synonyms=list(column.synonyms or []),
                    sensitivity=column.sensitivity,
                    hidden_for_llm=column.hidden_for_llm,
                )
                for column in sorted(table.columns, key=lambda item: item.ordinal_position)
                if column.status == "active"
            ],
            relationships=[
                KnowledgeRelationshipRead.model_validate(relationship)
                for relationship in relationships
            ],
        )

    def _persist_snapshot(
        self,
        db: Session,
        database_id: str,
        scan_run_id: str,
        *,
        introspected_tables: list[dict[str, Any]],
        introspected_relationships: list[dict[str, Any]],
    ) -> dict[str, Any]:
        existing_tables = {
            (item.schema_name, item.table_name): item
            for item in db.query(DatabaseKnowledgeTableModel)
            .filter(DatabaseKnowledgeTableModel.database_id == database_id)
            .all()
        }
        existing_columns = {
            (item.schema_name, item.table_name, item.column_name): item
            for item in db.query(DatabaseKnowledgeColumnModel)
            .filter(DatabaseKnowledgeColumnModel.database_id == database_id)
            .all()
        }
        existing_relationships = {
            (
                item.from_schema_name,
                item.from_table_name,
                item.from_column_name,
                item.to_schema_name,
                item.to_table_name,
                item.to_column_name,
                item.relation_type,
            ): item
            for item in db.query(DatabaseKnowledgeRelationshipModel)
            .filter(DatabaseKnowledgeRelationshipModel.database_id == database_id)
            .all()
        }

        active_table_keys: set[tuple[str, str]] = set()
        active_column_keys: set[tuple[str, str, str]] = set()
        active_relationship_keys: set[tuple[str, str, str, str, str, str, str]] = set()
        summary = {
            "tables_added": 0,
            "tables_updated": 0,
            "tables_removed": 0,
            "columns_added": 0,
            "columns_updated": 0,
            "columns_removed": 0,
            "relationships_added": 0,
            "relationships_updated": 0,
            "relationships_removed": 0,
        }

        for table_payload in introspected_tables:
            table_key = (str(table_payload["schema_name"]), str(table_payload["table_name"]))
            active_table_keys.add(table_key)
            table = existing_tables.get(table_key)
            if table is None:
                table = DatabaseKnowledgeTableModel(
                    database_id=database_id,
                    schema_name=table_key[0],
                    table_name=table_key[1],
                )
                db.add(table)
                existing_tables[table_key] = table
                summary["tables_added"] += 1
            else:
                summary["tables_updated"] += 1

            table.object_type = str(table_payload["object_type"])
            table.status = "active"
            table.column_count = len(list(table_payload["columns"]))
            table.row_count = table_payload["row_count"]
            table.primary_key = list(table_payload["primary_key"])
            table.description_auto = self._default_table_description(table.table_name, table.schema_name)
            table.business_meaning_auto = self._default_business_meaning(table.table_name)
            table.domain_auto = self._default_domain(table.table_name, table.schema_name)
            table.last_seen_scan_run_id = scan_run_id
            db.flush()

            for column_payload in table_payload["columns"]:
                column_key = (
                    table.schema_name,
                    table.table_name,
                    str(column_payload["name"]),
                )
                active_column_keys.add(column_key)
                column = existing_columns.get(column_key)
                if column is None:
                    column = DatabaseKnowledgeColumnModel(
                        database_id=database_id,
                        table_id=table.id,
                        schema_name=table.schema_name,
                        table_name=table.table_name,
                        column_name=column_key[2],
                        data_type=str(column_payload["type"]),
                    )
                    db.add(column)
                    existing_columns[column_key] = column
                    summary["columns_added"] += 1
                else:
                    summary["columns_updated"] += 1

                column.table_id = table.id
                column.data_type = str(column_payload["type"])
                column.ordinal_position = int(column_payload["ordinal_position"])
                column.is_nullable = bool(column_payload["nullable"])
                column.default_value = column_payload["default"]
                column.status = "active"
                column.sample_values = list(column_payload["sample_values"])
                column.description_auto = self._default_column_description(table.table_name, column.column_name)
                column.semantic_label_auto = self._default_semantic_label(column.column_name)
                column.last_seen_scan_run_id = scan_run_id

        for relationship_payload in introspected_relationships:
            relationship_key = (
                str(relationship_payload["from_schema_name"]),
                str(relationship_payload["from_table_name"]),
                str(relationship_payload["from_column_name"]),
                str(relationship_payload["to_schema_name"]),
                str(relationship_payload["to_table_name"]),
                str(relationship_payload["to_column_name"]),
                str(relationship_payload["relation_type"]),
            )
            active_relationship_keys.add(relationship_key)
            relationship = existing_relationships.get(relationship_key)
            if relationship is None:
                relationship = DatabaseKnowledgeRelationshipModel(
                    database_id=database_id,
                    from_schema_name=relationship_key[0],
                    from_table_name=relationship_key[1],
                    from_column_name=relationship_key[2],
                    to_schema_name=relationship_key[3],
                    to_table_name=relationship_key[4],
                    to_column_name=relationship_key[5],
                    relation_type=relationship_key[6],
                )
                db.add(relationship)
                existing_relationships[relationship_key] = relationship
                summary["relationships_added"] += 1
            else:
                summary["relationships_updated"] += 1

            relationship.cardinality = relationship_payload["cardinality"]
            relationship.confidence = float(relationship_payload["confidence"])
            relationship.status = "active"
            relationship.last_seen_scan_run_id = scan_run_id

        for table_key, table in existing_tables.items():
            if table_key in active_table_keys:
                continue
            if table.status != "deleted":
                summary["tables_removed"] += 1
            table.status = "deleted"
            table.last_seen_scan_run_id = scan_run_id

        for column_key, column in existing_columns.items():
            if column_key in active_column_keys:
                continue
            if column.status != "deleted":
                summary["columns_removed"] += 1
            column.status = "deleted"
            column.last_seen_scan_run_id = scan_run_id

        for relationship_key, relationship in existing_relationships.items():
            if relationship_key in active_relationship_keys:
                continue
            if relationship.status != "deleted":
                summary["relationships_removed"] += 1
            relationship.status = "deleted"
            relationship.last_seen_scan_run_id = scan_run_id

        summary["active_tables"] = len(active_table_keys)
        summary["active_columns"] = len(active_column_keys)
        summary["active_relationships"] = len(active_relationship_keys)
        db.commit()
        return summary

    def _resolve_target(self, db: Session, database_id: str) -> _ResolvedTarget:
        if database_id == settings.demo_database_id:
            return _ResolvedTarget(
                database_id=settings.demo_database_id,
                database_label=settings.demo_database_name,
                dialect=analytics_engine.dialect.name,
                allowed_tables=set(settings.allowed_tables) if settings.allowed_tables else None,
                engine=analytics_engine,
                dispose_on_close=False,
            )

        connection = (
            db.query(DatabaseConnectionModel)
            .filter(DatabaseConnectionModel.id == database_id)
            .first()
        )
        if connection is None:
            raise ValueError("Database connection not found.")

        engine = create_connection_engine(
            DatabaseConnectionPayload(
                dialect=connection.dialect,
                host=connection.host,
                port=connection.port,
                database=connection.database,
                username=connection.username,
                password=connection.password,
            )
        )
        return _ResolvedTarget(
            database_id=connection.id,
            database_label=connection.name,
            dialect=connection.dialect,
            allowed_tables=set(connection.allowed_tables or []) or None,
            engine=engine,
            dispose_on_close=True,
        )

    def _list_schemas(self, inspector, dialect: str) -> list[str]:
        try:
            schemas = [str(item) for item in inspector.get_schema_names()]
        except Exception:  # noqa: BLE001
            schemas = []

        filtered = [schema for schema in schemas if schema and schema not in SYSTEM_SCHEMAS]
        if not filtered:
            return [self._default_schema(dialect)]
        return filtered

    def _default_schema(self, dialect: str) -> str:
        return "public" if dialect.startswith("postgres") else "main"

    def _safe_row_count(self, engine, schema_name: str, table_name: str) -> int | None:
        try:
            table = Table(table_name, MetaData(), schema=schema_name, autoload_with=engine)
            with engine.connect() as connection:
                return int(connection.execute(select(func.count()).select_from(table)).scalar_one())
        except Exception:  # noqa: BLE001
            return None

    def _safe_sample_values(
        self,
        engine,
        schema_name: str,
        table_name: str,
        column_names: list[str],
    ) -> dict[str, list[str]]:
        if not column_names:
            return {}
        try:
            table = Table(table_name, MetaData(), schema=schema_name, autoload_with=engine)
            with engine.connect() as connection:
                rows = (
                    connection.execute(select(table).limit(SAMPLE_ROW_LIMIT))
                    .mappings()
                    .all()
                )
        except Exception:  # noqa: BLE001
            return {}

        sample_values: dict[str, list[str]] = {name: [] for name in column_names}
        for row in rows:
            for name in column_names:
                value = self._stringify_scalar(row.get(name))
                if value is None:
                    continue
                current = sample_values.setdefault(name, [])
                if value in current:
                    continue
                current.append(value)
                if len(current) > SAMPLE_VALUE_LIMIT:
                    del current[SAMPLE_VALUE_LIMIT:]
        return sample_values

    def _stringify_scalar(self, value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, (bytes, bytearray)):
            return None
        text = str(value).strip()
        if not text:
            return None
        return text[:120]

    def _default_table_description(self, table_name: str, schema_name: str) -> str:
        readable = table_name.replace("_", " ")
        return f"Auto-imported table {schema_name}.{table_name} ({readable})."

    def _default_business_meaning(self, table_name: str) -> str:
        readable = table_name.replace("_", " ")
        return f"Candidate business entity derived from the physical table name: {readable}."

    def _default_domain(self, table_name: str, schema_name: str) -> str:
        if schema_name not in {"public", "main"}:
            return schema_name
        if "_" in table_name:
            return table_name.split("_", 1)[0]
        return "core"

    def _default_column_description(self, table_name: str, column_name: str) -> str:
        return f"Column {column_name} from table {table_name}."

    def _default_semantic_label(self, column_name: str) -> str:
        return column_name.lower().strip()
