from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from sqlalchemy.orm import Session

from app.db.models import DatabaseConnectionModel
from app.schemas.semantic_catalog import (
    AggregationName,
    AnalyticsRole,
    SemanticColumn,
    SemanticTable,
    SemanticType,
    TableRole,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DRIVEE_NOTES_PATH = REPO_ROOT / "db-samples" / "notes.md"
_COLUMN_BULLET_RE = re.compile(r"^- `([^`]+)`\s+—\s+(.+)$", re.MULTILINE)


@dataclass(frozen=True)
class ColumnSemanticSeed:
    label: str | None = None
    business_description: str | None = None
    semantic_types: tuple[SemanticType, ...] = ()
    analytics_roles: tuple[AnalyticsRole, ...] = ()
    synonyms: tuple[str, ...] = ()
    value_type: str | None = None
    aggregation: tuple[AggregationName, ...] = ()
    filterable: bool | None = None
    groupable: bool | None = None
    sortable: bool | None = None


@dataclass(frozen=True)
class TableSemanticSeed:
    label: str | None = None
    business_description: str | None = None
    table_role: TableRole | None = None
    grain: str | None = None
    main_date_column: str | None = None
    main_entity: str | None = None
    synonyms: tuple[str, ...] = ()
    important_metrics: tuple[str, ...] = ()
    important_dimensions: tuple[str, ...] = ()
    columns: Mapping[str, ColumnSemanticSeed] = field(default_factory=dict)


@dataclass(frozen=True)
class SemanticSeedBundle:
    database_description: str | None = None
    source_path: str | None = None
    tables: Mapping[str, TableSemanticSeed] = field(default_factory=dict)


def resolve_database_semantic_seed(db: Session, database_id: str) -> SemanticSeedBundle | None:
    connection = (
        db.query(DatabaseConnectionModel)
        .filter(DatabaseConnectionModel.id == database_id)
        .first()
    )
    if connection is None:
        return None

    name_parts = [
        str(connection.name or "").lower(),
        str(connection.database or "").lower(),
        str(connection.description or "").lower(),
    ]
    if not any("drivee" in part for part in name_parts):
        return None

    return load_drivee_semantic_seed(DEFAULT_DRIVEE_NOTES_PATH)


def load_drivee_semantic_seed(notes_path: Path = DEFAULT_DRIVEE_NOTES_PATH) -> SemanticSeedBundle | None:
    if not notes_path.exists():
        return None

    notes_text = notes_path.read_text(encoding="utf-8").strip()
    if not notes_text:
        return None

    column_descriptions = _parse_column_descriptions(notes_text)
    interpretation_notes = _parse_interpretation_notes(notes_text)

    table_description = (
        "Факт-таблица заказов и тендеров сервиса ride-hailing. "
        + " ".join(
            note
            for note in interpretation_notes
            if note
        )
    ).strip()

    table_seed = TableSemanticSeed(
        label="Заказы и тендеры",
        business_description=table_description,
        table_role="fact",
        grain=_first_matching_note(interpretation_notes, "одна строка") or "Одна строка = одна комбинация order_id и tender_id.",
        main_date_column="order_timestamp",
        main_entity="заказ / тендер",
        synonyms=(
            "заказы",
            "заказов",
            "тендеры",
            "тендеров",
            "поездки",
            "поездок",
            "ride hailing",
            "incity orders",
        ),
        important_metrics=(
            "distance_in_meters",
            "duration_in_seconds",
            "price_order_local",
            "price_tender_local",
            "price_start_local",
        ),
        important_dimensions=(
            "city_id",
            "order_id",
            "tender_id",
            "user_id",
            "driver_id",
            "status_order",
            "status_tender",
            "order_timestamp",
            "tender_timestamp",
            "driveraccept_timestamp",
            "driverarrived_timestamp",
            "driverstarttheride_timestamp",
            "driverdone_timestamp",
        ),
        columns={
            "city_id": ColumnSemanticSeed(
                label="Город",
                business_description=column_descriptions.get("city_id"),
                semantic_types=("id", "dimension", "location"),
                analytics_roles=("default_filter", "default_group_by"),
                synonyms=("город", "города", "city", "city id", "идентификатор города"),
                value_type="identifier",
                aggregation=("count", "count_distinct"),
                groupable=True,
            ),
            "order_id": ColumnSemanticSeed(
                label="Заказ",
                business_description=column_descriptions.get("order_id"),
                semantic_types=("id", "dimension", "countable_entity"),
                analytics_roles=("default_filter",),
                synonyms=(
                    "заказ",
                    "заказы",
                    "заказов",
                    "id заказа",
                    "идентификатор заказа",
                    "количество заказов",
                    "число заказов",
                    "созданные заказы",
                    "созданных заказов",
                ),
                value_type="identifier",
                aggregation=("count", "count_distinct"),
                groupable=True,
            ),
            "tender_id": ColumnSemanticSeed(
                label="Тендер",
                business_description=column_descriptions.get("tender_id"),
                semantic_types=("id", "dimension", "countable_entity"),
                analytics_roles=("default_filter",),
                synonyms=("тендер", "тендеры", "тендеров", "id тендера", "идентификатор тендера"),
                value_type="identifier",
                aggregation=("count", "count_distinct"),
                groupable=True,
            ),
            "user_id": ColumnSemanticSeed(
                label="Пользователь",
                business_description=column_descriptions.get("user_id"),
                semantic_types=("id", "dimension", "countable_entity"),
                analytics_roles=("default_filter", "default_group_by"),
                synonyms=("пользователь", "пользователи", "пассажир", "пассажиры", "клиент", "клиенты"),
                value_type="identifier",
                aggregation=("count", "count_distinct"),
                groupable=True,
            ),
            "driver_id": ColumnSemanticSeed(
                label="Водитель",
                business_description=column_descriptions.get("driver_id"),
                semantic_types=("id", "dimension", "countable_entity"),
                analytics_roles=("default_filter", "default_group_by"),
                synonyms=(
                    "водитель",
                    "водители",
                    "водителей",
                    "водителям",
                    "по водителям",
                    "driver",
                    "id водителя",
                    "идентификатор водителя",
                ),
                value_type="identifier",
                aggregation=("count", "count_distinct"),
                groupable=True,
            ),
            "offset_hours": ColumnSemanticSeed(
                label="Смещение UTC (часы)",
                business_description=column_descriptions.get("offset_hours"),
                semantic_types=("dimension",),
                analytics_roles=("default_filter",),
                synonyms=("смещение utc", "часовой пояс", "timezone offset", "offset hours"),
                value_type="numeric",
                aggregation=("avg", "min", "max"),
                groupable=True,
            ),
            "status_order": ColumnSemanticSeed(
                label="Статус заказа",
                business_description=(
                    "итоговый статус заказа. "
                    "Для завершённых заказов используй значение 'done', для отменённых — 'cancel'."
                ),
                semantic_types=("status", "dimension"),
                analytics_roles=("default_filter", "default_group_by"),
                synonyms=(
                    "статус заказа",
                    "итоговый статус",
                    "заказ завершён",
                    "заказ отменён",
                    "done",
                    "completed",
                    "completed orders",
                    "cancel",
                ),
                value_type="status",
                aggregation=("count", "count_distinct"),
                groupable=True,
            ),
            "status_tender": ColumnSemanticSeed(
                label="Статус тендера",
                business_description=(
                    "статус тендера или процесса подбора водителя. "
                    "Типичные значения в этих данных: 'done', 'decline', 'cancel'."
                ),
                semantic_types=("status", "dimension"),
                analytics_roles=("default_filter", "default_group_by"),
                synonyms=("статус тендера", "тендер", "подбор водителя", "статус подбора", "done", "decline", "cancel"),
                value_type="status",
                aggregation=("count", "count_distinct"),
                groupable=True,
            ),
            "order_timestamp": ColumnSemanticSeed(
                label="Создание заказа",
                business_description=column_descriptions.get("order_timestamp"),
                semantic_types=("datetime",),
                analytics_roles=("time_axis",),
                synonyms=("создание заказа", "время заказа", "дата заказа", "созданные заказы", "созданных заказов"),
                value_type="datetime",
                aggregation=("min", "max", "count"),
                groupable=True,
            ),
            "tender_timestamp": ColumnSemanticSeed(
                label="Создание тендера",
                business_description=column_descriptions.get("tender_timestamp"),
                semantic_types=("datetime",),
                analytics_roles=("time_axis",),
                synonyms=("создание тендера", "время тендера", "начало тендера"),
                value_type="datetime",
                aggregation=("min", "max", "count"),
                groupable=True,
            ),
            "driveraccept_timestamp": ColumnSemanticSeed(
                label="Принятие водителем",
                business_description="время принятия заказа водителем. Если поле не NULL, заказ считается принятым водителем.",
                semantic_types=("datetime",),
                analytics_roles=("time_axis",),
                synonyms=(
                    "принятие водителем",
                    "водитель принял",
                    "accept",
                    "accepted",
                    "принятые заказы",
                    "принятых заказов",
                    "принятые поездки",
                    "принятых поездок",
                ),
                value_type="datetime",
                aggregation=("min", "max", "count"),
                groupable=True,
            ),
            "driverarrived_timestamp": ColumnSemanticSeed(
                label="Прибытие водителя",
                business_description=column_descriptions.get("driverarrived_timestamp"),
                semantic_types=("datetime",),
                analytics_roles=("time_axis",),
                synonyms=("прибытие водителя", "подача", "время подачи", "driver arrived", "arrival"),
                value_type="datetime",
                aggregation=("min", "max", "count"),
                groupable=True,
            ),
            "driverstarttheride_timestamp": ColumnSemanticSeed(
                label="Старт поездки",
                business_description=column_descriptions.get("driverstarttheride_timestamp"),
                semantic_types=("datetime",),
                analytics_roles=("time_axis",),
                synonyms=("старт поездки", "начало поездки", "ride start"),
                value_type="datetime",
                aggregation=("min", "max", "count"),
                groupable=True,
            ),
            "driverdone_timestamp": ColumnSemanticSeed(
                label="Завершение поездки",
                business_description="время завершения поездки. Если поле не NULL, поездка завершена; обычно это соответствует status_order = 'done'.",
                semantic_types=("datetime",),
                analytics_roles=("time_axis",),
                synonyms=(
                    "завершение поездки",
                    "окончание поездки",
                    "ride done",
                    "completed ride",
                    "completed rides",
                    "завершённые поездки",
                    "завершенных поездок",
                    "завершённых поездок",
                    "не завершённые поездки",
                    "не завершенные поездки",
                ),
                value_type="datetime",
                aggregation=("min", "max", "count"),
                groupable=True,
            ),
            "clientcancel_timestamp": ColumnSemanticSeed(
                label="Отмена клиентом",
                business_description=column_descriptions.get("clientcancel_timestamp"),
                semantic_types=("datetime",),
                analytics_roles=("time_axis",),
                synonyms=("отмена клиентом", "клиент отменил", "client cancel"),
                value_type="datetime",
                aggregation=("min", "max", "count"),
                groupable=True,
            ),
            "drivercancel_timestamp": ColumnSemanticSeed(
                label="Отмена водителем",
                business_description=column_descriptions.get("drivercancel_timestamp"),
                semantic_types=("datetime",),
                analytics_roles=("time_axis",),
                synonyms=("отмена водителем", "водитель отменил", "driver cancel"),
                value_type="datetime",
                aggregation=("min", "max", "count"),
                groupable=True,
            ),
            "order_modified_local": ColumnSemanticSeed(
                label="Последнее изменение заказа",
                business_description=column_descriptions.get("order_modified_local"),
                semantic_types=("datetime",),
                analytics_roles=("time_axis",),
                synonyms=("последнее изменение заказа", "изменение заказа", "updated order"),
                value_type="datetime",
                aggregation=("min", "max", "count"),
                groupable=True,
            ),
            "cancel_before_accept_local": ColumnSemanticSeed(
                label="Отмена до принятия",
                business_description=column_descriptions.get("cancel_before_accept_local"),
                semantic_types=("datetime",),
                analytics_roles=("time_axis",),
                synonyms=("отмена до принятия", "клиент отменил до принятия", "cancel before accept"),
                value_type="datetime",
                aggregation=("min", "max", "count"),
                groupable=True,
            ),
            "distance_in_meters": ColumnSemanticSeed(
                label="Расстояние (м)",
                business_description=column_descriptions.get("distance_in_meters"),
                semantic_types=("metric",),
                analytics_roles=("primary_metric",),
                synonyms=("расстояние", "дистанция", "distance"),
                value_type="numeric",
                aggregation=("sum", "avg", "min", "max"),
            ),
            "duration_in_seconds": ColumnSemanticSeed(
                label="Длительность (сек)",
                business_description=column_descriptions.get("duration_in_seconds"),
                semantic_types=("duration", "metric"),
                analytics_roles=("supporting_metric",),
                synonyms=("длительность", "длительность поездки", "время поездки", "duration", "ride duration"),
                value_type="duration",
                aggregation=("avg", "min", "max"),
            ),
            "price_order_local": ColumnSemanticSeed(
                label="Стоимость заказа",
                business_description=column_descriptions.get("price_order_local"),
                semantic_types=("currency", "metric"),
                analytics_roles=("primary_metric",),
                synonyms=("стоимость заказа", "цена заказа", "order price"),
                value_type="currency",
                aggregation=("sum", "avg", "min", "max"),
            ),
            "price_tender_local": ColumnSemanticSeed(
                label="Стоимость тендера",
                business_description=column_descriptions.get("price_tender_local"),
                semantic_types=("currency", "metric"),
                analytics_roles=("primary_metric",),
                synonyms=("стоимость тендера", "цена тендера", "tender price"),
                value_type="currency",
                aggregation=("sum", "avg", "min", "max"),
            ),
            "price_start_local": ColumnSemanticSeed(
                label="Стартовая стоимость",
                business_description=column_descriptions.get("price_start_local"),
                semantic_types=("currency", "metric"),
                analytics_roles=("primary_metric",),
                synonyms=("стартовая стоимость", "стоимость на старте", "start price"),
                value_type="currency",
                aggregation=("sum", "avg", "min", "max"),
            ),
        },
    )

    return SemanticSeedBundle(
        database_description=notes_text,
        source_path=str(notes_path),
        tables={"train": table_seed},
    )


def apply_table_semantic_seed(table: SemanticTable, seed: TableSemanticSeed) -> SemanticTable:
    updated_columns: list[SemanticColumn] = []
    for column in table.columns:
        column_seed = seed.columns.get(column.column_name)
        if column_seed is None:
            updated_columns.append(column)
            continue
        updated_columns.append(_apply_column_seed(column, column_seed))

    update_payload = {"columns": updated_columns}
    if seed.label:
        update_payload["label"] = seed.label
    if seed.business_description:
        update_payload["business_description"] = seed.business_description
    if seed.table_role:
        update_payload["table_role"] = seed.table_role
    if seed.grain:
        update_payload["grain"] = seed.grain
    if seed.main_date_column:
        update_payload["main_date_column"] = seed.main_date_column
    if seed.main_entity:
        update_payload["main_entity"] = seed.main_entity
    if seed.synonyms:
        update_payload["synonyms"] = sorted({*table.synonyms, *seed.synonyms})
    if seed.important_metrics:
        update_payload["important_metrics"] = list(seed.important_metrics)
    if seed.important_dimensions:
        update_payload["important_dimensions"] = list(seed.important_dimensions)
    return table.model_copy(update=update_payload)


def _apply_column_seed(column: SemanticColumn, seed: ColumnSemanticSeed) -> SemanticColumn:
    update_payload = {}
    if seed.label:
        update_payload["label"] = seed.label
    if seed.business_description:
        update_payload["business_description"] = seed.business_description
    if seed.semantic_types:
        update_payload["semantic_types"] = list(seed.semantic_types)
    if seed.analytics_roles:
        update_payload["analytics_roles"] = list(seed.analytics_roles)
    if seed.synonyms:
        update_payload["synonyms"] = sorted({*column.synonyms, *seed.synonyms})
    if seed.value_type:
        update_payload["value_type"] = seed.value_type
    if seed.aggregation:
        update_payload["aggregation"] = list(seed.aggregation)
    if seed.filterable is not None:
        update_payload["filterable"] = seed.filterable
    if seed.groupable is not None:
        update_payload["groupable"] = seed.groupable
    if seed.sortable is not None:
        update_payload["sortable"] = seed.sortable
    return column.model_copy(update=update_payload)


def _parse_column_descriptions(notes_text: str) -> dict[str, str]:
    return {
        column_name.strip(): description.strip()
        for column_name, description in _COLUMN_BULLET_RE.findall(notes_text)
    }


def _parse_interpretation_notes(notes_text: str) -> list[str]:
    lines = notes_text.splitlines()
    notes: list[str] = []
    in_section = False
    for raw_line in lines:
        line = raw_line.strip()
        if line.startswith("## "):
            in_section = line.lower() == "## как интерпретировать данные"
            continue
        if not in_section or not line.startswith("- "):
            continue
        notes.append(line[2:].strip())
    return notes


def _first_matching_note(notes: list[str], needle: str) -> str | None:
    lowered_needle = needle.lower()
    for note in notes:
        if lowered_needle in note.lower():
            return note
    return None
