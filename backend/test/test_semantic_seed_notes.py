from __future__ import annotations

from pathlib import Path

from app.schemas.semantic_catalog import ColumnProfile, SemanticColumn, SemanticTable
from app.services.semantic_seed_notes import apply_table_semantic_seed, load_drivee_semantic_seed


def _notes_path() -> Path:
    return Path(__file__).resolve().parents[2] / "db-samples" / "notes.md"


def test_load_drivee_seed_uses_notes_for_grain_and_column_descriptions() -> None:
    seed = load_drivee_semantic_seed(_notes_path())

    assert seed is not None
    assert seed.database_description is not None
    assert "Одна строка соответствует одной комбинации `order_id` и `tender_id`." in seed.database_description
    table_seed = seed.tables["train"]
    assert table_seed.grain == "Одна строка соответствует одной комбинации `order_id` и `tender_id`."
    assert table_seed.columns["driver_id"].business_description == "анонимизированный идентификатор водителя."


def test_apply_table_seed_overrides_wrong_grain_and_column_roles() -> None:
    seed = load_drivee_semantic_seed(_notes_path())
    assert seed is not None

    source_table = SemanticTable(
        schema_name="public",
        table_name="train",
        label="Ride Fact",
        business_description="Fact table containing one row per ride.",
        table_role="fact",
        grain="one row = one ride",
        main_date_column="order_timestamp",
        main_entity="Ride",
        synonyms=["Ride"],
        important_metrics=["distance_in_meters"],
        important_dimensions=["driver_id"],
        columns=[
            SemanticColumn(
                schema_name="public",
                table_name="train",
                column_name="driver_id",
                label="Driver ID",
                business_description="Identifier of the driver assigned to the order.",
                semantic_types=["foreign_key"],
                analytics_roles=["default_filter"],
                value_type="identifier",
                aggregation=["count", "count_distinct"],
                groupable=True,
                synonyms=["driver_id"],
                example_values=[],
                data_type="TEXT",
                profile=ColumnProfile(),
            ),
            SemanticColumn(
                schema_name="public",
                table_name="train",
                column_name="duration_in_seconds",
                label="Duration (seconds)",
                business_description="Total ride duration in seconds.",
                semantic_types=["ratio"],
                analytics_roles=["supporting_metric"],
                value_type="ratio",
                aggregation=["avg"],
                synonyms=["duration_in_seconds"],
                example_values=[],
                data_type="INTEGER",
                profile=ColumnProfile(),
            ),
        ],
    )

    updated = apply_table_semantic_seed(source_table, seed.tables["train"])
    driver_column = next(column for column in updated.columns if column.column_name == "driver_id")
    duration_column = next(column for column in updated.columns if column.column_name == "duration_in_seconds")

    assert updated.label == "Заказы и тендеры"
    assert updated.grain == "Одна строка соответствует одной комбинации `order_id` и `tender_id`."
    assert updated.main_entity == "заказ / тендер"
    assert "тендеров" in updated.synonyms
    assert driver_column.label == "Водитель"
    assert driver_column.business_description == "анонимизированный идентификатор водителя."
    assert driver_column.semantic_types == ["id", "dimension", "countable_entity"]
    assert duration_column.semantic_types == ["duration", "metric"]
    assert duration_column.value_type == "duration"
