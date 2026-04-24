from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import (
    DatabaseConnectionModel,
    DatabaseKnowledgeColumnModel,
    DatabaseKnowledgeTableModel,
    SemanticDictionaryModel,
)
from app.services.dictionary_service import DictionaryService
from app.services.knowledge_service import KnowledgeService, _ResolvedTarget
from app.services.semantic_catalog_service import SemanticCatalogService


def _build_session() -> tuple[Session, object]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal(), engine


def test_knowledge_summary_exposes_persisted_database_description(monkeypatch) -> None:
    db, engine = _build_session()
    service = KnowledgeService()

    monkeypatch.setattr(
        service,
        "_resolve_target",
        lambda _db, database_id: _ResolvedTarget(
            database_id=database_id,
            database_label="Demo DB",
            dialect="sqlite",
            allowed_tables=None,
            engine=engine,
            dispose_on_close=False,
        ),
    )

    service.set_database_description(db, "db1", "Описание предметной области")
    summary = service.get_summary(db, "db1")

    assert summary.database_description == "Описание предметной области"
    assert summary.database_label == "Demo DB"


def test_dictionary_service_filters_by_database_id_and_legacy_label() -> None:
    db, _engine = _build_session()
    db.add(DatabaseConnectionModel(id="db1", name="Demo DB", dialect="sqlite"))
    db.add_all(
        [
            SemanticDictionaryModel(
                term="orders",
                synonyms=["заказы"],
                mapped_expression="orders",
                description="legacy",
                source_database="Demo DB",
            ),
            SemanticDictionaryModel(
                term="revenue",
                synonyms=["выручка"],
                mapped_expression="SUM(orders.amount)",
                description="new",
                database_id="db1",
                source_database="Demo DB",
            ),
        ]
    )
    db.commit()

    entries = DictionaryService().list_entries(db, database_id="db1")

    assert [entry.term for entry in entries] == ["orders", "revenue"]


def test_semantic_catalog_uses_knowledge_manual_overrides_and_hides_llm_columns(
    monkeypatch,
) -> None:
    db, engine = _build_session()
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE orders (
              id INTEGER PRIMARY KEY,
              customer_name TEXT,
              internal_note TEXT,
              created_at TEXT
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO orders (id, customer_name, internal_note, created_at)
            VALUES
              (1, 'Alice', 'private', '2024-01-01'),
              (2, 'Bob', 'internal', '2024-01-02')
            """
        )

    db.add(DatabaseConnectionModel(id="db1", name="Demo DB", dialect="sqlite"))
    db.flush()
    table = DatabaseKnowledgeTableModel(
        database_id="db1",
        schema_name="main",
        table_name="orders",
        object_type="table",
        status="active",
        column_count=4,
        row_count=2,
        primary_key=["id"],
        description_manual="Заказы клиентов.",
        semantic_label_manual="Заказы",
        semantic_table_role_manual="fact",
        semantic_grain_manual="one row = one order",
        semantic_main_date_column_manual="created_at",
        semantic_main_entity_manual="заказ",
        semantic_synonyms=["покупки", "заказы"],
        semantic_important_metrics=["total_orders"],
        semantic_important_dimensions=["customer_name"],
    )
    db.add(table)
    db.flush()
    db.add_all(
        [
            DatabaseKnowledgeColumnModel(
                database_id="db1",
                table_id=table.id,
                schema_name="main",
                table_name="orders",
                column_name="id",
                data_type="INTEGER",
                ordinal_position=1,
                is_nullable=False,
                status="active",
            ),
            DatabaseKnowledgeColumnModel(
                database_id="db1",
                table_id=table.id,
                schema_name="main",
                table_name="orders",
                column_name="customer_name",
                data_type="TEXT",
                ordinal_position=2,
                is_nullable=True,
                status="active",
                semantic_label_manual="Клиент",
                description_manual="Имя клиента в заказе.",
                synonyms=["клиент"],
                sample_values=["Alice", "Bob"],
            ),
            DatabaseKnowledgeColumnModel(
                database_id="db1",
                table_id=table.id,
                schema_name="main",
                table_name="orders",
                column_name="internal_note",
                data_type="TEXT",
                ordinal_position=3,
                is_nullable=True,
                status="active",
                hidden_for_llm=True,
            ),
            DatabaseKnowledgeColumnModel(
                database_id="db1",
                table_id=table.id,
                schema_name="main",
                table_name="orders",
                column_name="created_at",
                data_type="TEXT",
                ordinal_position=4,
                is_nullable=True,
                status="active",
            ),
        ]
    )
    db.commit()

    service = SemanticCatalogService()
    monkeypatch.setattr(service.llm_service, "_configured_for_model", lambda _model: False)
    monkeypatch.setattr(
        "app.services.semantic_catalog_service.resolve_engine",
        lambda _db, _database_id: engine,
    )
    monkeypatch.setattr(
        "app.services.semantic_catalog_service.resolve_dialect",
        lambda _db, _database_id: "sqlite",
    )
    monkeypatch.setattr(
        "app.services.semantic_catalog_service.resolve_allowed_tables",
        lambda _db, _database_id, _engine: ["orders"],
    )

    catalog = service.build_catalog(db, "db1", database_description="Продажи")
    semantic_table = catalog.tables[0]
    column_names = [column.column_name for column in semantic_table.columns]
    customer_column = next(
        column for column in semantic_table.columns if column.column_name == "customer_name"
    )

    assert semantic_table.label == "Заказы"
    assert semantic_table.business_description == "Заказы клиентов."
    assert semantic_table.table_role == "fact"
    assert semantic_table.grain == "one row = one order"
    assert semantic_table.main_date_column == "created_at"
    assert semantic_table.main_entity == "заказ"
    assert semantic_table.synonyms == ["покупки", "заказы"]
    assert semantic_table.important_metrics == ["total_orders"]
    assert semantic_table.important_dimensions == ["customer_name"]
    assert "internal_note" not in column_names
    assert customer_column.label == "Клиент"
    assert customer_column.business_description == "Имя клиента в заказе."
    assert customer_column.synonyms == ["клиент"]
