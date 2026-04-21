from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DashboardModel, DatabaseConnectionModel, WidgetModel
from app.services.dashboard_types import DashboardWidgetSnapshot, GridLayout, WidgetKind, WidgetPreviewResult
from app.services.database_resolution import resolve_engine


class DashboardSnapshotService:
    PREVIEW_ROW_LIMIT = 20
    PREVIEW_QUERY_LIMIT = 21

    def collect_snapshots(self, db: Session, dashboard: DashboardModel) -> list[DashboardWidgetSnapshot]:
        snapshots: list[DashboardWidgetSnapshot] = []
        for dw in dashboard.dashboard_widgets:
            if dw.widget.deleted_at is not None:
                continue
            widget = dw.widget
            layout = GridLayout.from_mapping(dw.layout or {})
            if widget.source_type == WidgetKind.TEXT.value:
                snapshots.append(
                    DashboardWidgetSnapshot(
                        title=dw.title_override or widget.title,
                        kind=WidgetKind.TEXT,
                        layout=layout,
                        body=widget.description or widget.sql_text or "This dashboard is a living report.",
                        preview_rows=[],
                        columns=[],
                    )
                )
                continue

            run = max(
                widget.runs,
                key=lambda item: item.finished_at or item.started_at,
                default=None,
            )
            if run is None and widget.sql_text.strip():
                run = self.execute_widget_preview(db, widget)

            if run is None:
                snapshots.append(
                    DashboardWidgetSnapshot(
                        title=dw.title_override or widget.title,
                        kind=self._coerce_widget_kind(widget.visualization_type),
                        layout=layout,
                        body="No data available.",
                        preview_rows=[],
                        columns=[],
                    )
                )
                continue

            snapshots.append(
                DashboardWidgetSnapshot(
                    title=dw.title_override or widget.title,
                    kind=self._coerce_widget_kind(widget.visualization_type),
                    layout=layout,
                    body="",
                    preview_rows=run.rows_preview_json or [],
                    columns=run.columns_json or [],
                )
            )
        return snapshots

    def _coerce_widget_kind(self, value: str) -> WidgetKind:
        try:
            return WidgetKind(value)
        except Exception:  # noqa: BLE001
            return WidgetKind.TABLE

    def execute_widget_preview(self, db: Session, widget: WidgetModel) -> WidgetPreviewResult | None:
        conn_id = widget.database_connection_id
        if not conn_id:
            connection = (
                db.query(DatabaseConnectionModel.id)
                .order_by(DatabaseConnectionModel.created_at.asc())
                .first()
            )
            if connection is None:
                return None
            conn_id = connection[0]
        if not conn_id or not widget.sql_text.strip():
            return None

        engine = resolve_engine(db, conn_id)
        started = time.perf_counter()
        preview_sql = self._build_preview_sql(widget.sql_text)
        with engine.begin() as connection:
            self._apply_read_only_guards(connection)
            df: pd.DataFrame = pd.read_sql_query(sa_text(preview_sql), connection)
        elapsed = int((time.perf_counter() - started) * 1000)
        columns = [{"name": str(name), "type": str(df[name].dtype)} for name in df.columns]
        rows_full = json.loads(df.to_json(orient="records", date_format="iso"))
        rows_preview = rows_full[: self.PREVIEW_ROW_LIMIT]
        return WidgetPreviewResult(
            columns=columns,
            rows_preview=rows_preview,
            rows_preview_truncated=len(rows_full) > len(rows_preview),
            row_count=int(len(df.index)),
            execution_time_ms=elapsed,
        )

    def _build_preview_sql(self, sql_text: str) -> str:
        cleaned = sql_text.strip().rstrip(";")
        return f"SELECT * FROM ({cleaned}) AS dashboard_preview LIMIT {self.PREVIEW_QUERY_LIMIT}"

    def _apply_read_only_guards(self, connection: Any) -> None:
        dialect = connection.engine.dialect.name.lower()
        if dialect.startswith("postgres"):
            connection.exec_driver_sql("SET LOCAL default_transaction_read_only = on")
            connection.exec_driver_sql(f"SET LOCAL statement_timeout = {max(settings.query_timeout_seconds * 1000, 1000)}")
        elif dialect.startswith("sqlite"):
            connection.exec_driver_sql("PRAGMA query_only = ON")
