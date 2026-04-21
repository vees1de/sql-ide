from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DashboardModel, DashboardWidgetModel, WidgetModel
from app.services.dashboard_types import GridLayout


class DashboardLayoutService:
    GRID_COLUMNS = 12
    MIN_WIDGET_WIDTH = 2
    MIN_WIDGET_HEIGHT = 3
    GRID_Y_STEP = 1

    DEFAULT_TEXT_TITLE = "Dashboard notes"
    DEFAULT_TEXT_BODY = (
        "This dashboard is a living report. "
        "Use the share link below to open the interactive version, "
        "and export or schedule it for recurring delivery."
    )

    def ensure_default_text_widget(self, db: Session, dashboard: DashboardModel) -> DashboardWidgetModel | None:
        existing = next(
            (item for item in dashboard.dashboard_widgets if item.widget.source_type == "text" and item.widget.deleted_at is None),
            None,
        )
        if existing is not None:
            return existing

        max_row = 0
        for item in dashboard.dashboard_widgets:
            layout = item.layout or {}
            max_row = max(max_row, int(layout.get("y", 0)) + int(layout.get("h", 0)))

        widget = WidgetModel(
            title=self.DEFAULT_TEXT_TITLE,
            description=self.DEFAULT_TEXT_BODY,
            source_type="text",
            sql_text="",
            visualization_type="text",
            visualization_config={"kind": "dashboard_note"},
            refresh_policy="manual",
            is_public=dashboard.is_public,
            owner_id=dashboard.owner_id,
            database_connection_id=None,
        )
        db.add(widget)
        db.flush()

        dashboard_widget = DashboardWidgetModel(
            dashboard_id=dashboard.id,
            widget_id=widget.id,
            layout={"x": 0, "y": max_row, "w": 12, "h": 3},
            title_override=self.DEFAULT_TEXT_TITLE,
            display_options={"kind": "text", "variant": "note"},
        )
        db.add(dashboard_widget)
        db.flush()
        return dashboard_widget

    def place_widget_layout(
        self,
        dashboard: DashboardModel,
        desired_layout: dict[str, Any],
        exclude_dashboard_widget_id: str | None = None,
    ) -> dict[str, int]:
        layout = self._sanitize_layout(desired_layout)
        occupied = [
            self._sanitize_layout(item.layout)
            for item in dashboard.dashboard_widgets
            if item.id != exclude_dashboard_widget_id and item.widget.deleted_at is None
        ]
        while any(self._layouts_overlap(layout, item) for item in occupied):
            layout = GridLayout(layout.x, layout.y + self.GRID_Y_STEP, layout.w, layout.h)
        return layout.to_mapping()

    def normalize_dashboard_layouts(self, db: Session, dashboard: DashboardModel) -> bool:
        changed = False
        placed: list[GridLayout] = []
        for item in dashboard.dashboard_widgets:
            if item.widget.deleted_at is not None:
                continue
            next_layout = self._sanitize_layout(item.layout)
            while any(self._layouts_overlap(next_layout, other) for other in placed):
                next_layout = GridLayout(next_layout.x, next_layout.y + self.GRID_Y_STEP, next_layout.w, next_layout.h)
            if next_layout.to_mapping() != (item.layout or {}):
                item.layout = next_layout.to_mapping()
                changed = True
            placed.append(next_layout)
        if changed:
            db.flush()
        return changed

    def _sanitize_layout(self, layout: dict[str, Any]) -> GridLayout:
        raw = GridLayout.from_mapping(layout or {})
        x = max(0, raw.x)
        y = max(0, raw.y)
        w = max(self.MIN_WIDGET_WIDTH, raw.w)
        h = max(self.MIN_WIDGET_HEIGHT, raw.h)
        w = min(self.GRID_COLUMNS, w)
        x = min(x, self.GRID_COLUMNS - w)
        return GridLayout(x=x, y=y, w=w, h=h)

    def _layouts_overlap(self, left: GridLayout, right: GridLayout) -> bool:
        return not (
            left.x + left.w <= right.x
            or right.x + right.w <= left.x
            or left.y + left.h <= right.y
            or right.y + right.h <= left.y
        )
