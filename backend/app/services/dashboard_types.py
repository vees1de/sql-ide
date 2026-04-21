from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

MOSCOW_TZ = "Europe/Moscow"


class WidgetKind(str, Enum):
    TEXT = "text"
    METRIC = "metric"
    LINE = "line"
    AREA = "area"
    BAR = "bar"
    STACKED_BAR = "stacked_bar"
    PIE = "pie"
    TABLE = "table"


CHART_WIDGET_KINDS = {
    WidgetKind.LINE,
    WidgetKind.AREA,
    WidgetKind.BAR,
    WidgetKind.STACKED_BAR,
    WidgetKind.PIE,
}


_WEEKDAY_ALIASES = {
    "mon": "mon",
    "monday": "mon",
    "tue": "tue",
    "tues": "tue",
    "tuesday": "tue",
    "wed": "wed",
    "wednesday": "wed",
    "thu": "thu",
    "thurs": "thu",
    "thursday": "thu",
    "fri": "fri",
    "friday": "fri",
    "sat": "sat",
    "saturday": "sat",
    "sun": "sun",
    "sunday": "sun",
}


def normalize_weekday(value: str) -> str:
    key = str(value).strip().lower()
    return _WEEKDAY_ALIASES.get(key, key[:3])


@dataclass(frozen=True)
class GridLayout:
    x: int
    y: int
    w: int
    h: int

    @classmethod
    def from_mapping(cls, layout: dict[str, Any]) -> "GridLayout":
        return cls(
            x=int(layout.get("x") or 0),
            y=int(layout.get("y") or 0),
            w=int(layout.get("w") or 0),
            h=int(layout.get("h") or 0),
        )

    def to_mapping(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}


@dataclass(frozen=True)
class ChartPoint:
    label: str
    y: float
    raw: Any


@dataclass(frozen=True)
class ChartSeries:
    points: list[ChartPoint]
    x_key: str | None
    y_key: str | None
    minimum: float
    maximum: float


@dataclass(frozen=True)
class DashboardWidgetSnapshot:
    title: str
    kind: WidgetKind
    layout: GridLayout
    body: str
    preview_rows: list[dict[str, Any]]
    columns: list[dict[str, Any]]


@dataclass(frozen=True)
class WidgetPreviewResult:
    columns: list[dict[str, Any]]
    rows_preview: list[dict[str, Any]]
    rows_preview_truncated: bool
    row_count: int
    execution_time_ms: int
