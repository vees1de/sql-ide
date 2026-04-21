from __future__ import annotations

import json
import logging
import smtplib
import textwrap
from dataclasses import dataclass
from datetime import datetime, time
from email.message import EmailMessage
from io import BytesIO
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    DashboardModel,
    DashboardScheduleModel,
    DashboardWidgetModel,
    DatabaseConnectionModel,
    WidgetModel,
    WidgetRunModel,
)
from app.db.session import ServiceSessionLocal
from app.services.database_resolution import resolve_engine


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DashboardWidgetSnapshot:
    title: str
    kind: str
    layout: dict[str, Any]
    body: str
    preview_rows: list[dict[str, Any]]
    columns: list[dict[str, Any]]


class DashboardService:
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
            layout = {**layout, "y": layout["y"] + self.GRID_Y_STEP}
        return layout

    def normalize_dashboard_layouts(self, db: Session, dashboard: DashboardModel) -> bool:
        changed = False
        placed: list[dict[str, int]] = []
        for item in dashboard.dashboard_widgets:
            if item.widget.deleted_at is not None:
                continue
            next_layout = self._sanitize_layout(item.layout)
            while any(self._layouts_overlap(next_layout, other) for other in placed):
                next_layout = {**next_layout, "y": next_layout["y"] + self.GRID_Y_STEP}
            if next_layout != item.layout:
                item.layout = next_layout
                changed = True
            placed.append(next_layout)
        if changed:
            db.flush()
        return changed

    def upsert_schedule(
        self,
        db: Session,
        dashboard: DashboardModel,
        payload: dict[str, Any],
    ) -> DashboardScheduleModel:
        schedule = dashboard.schedule
        if schedule is None:
            schedule = DashboardScheduleModel(dashboard_id=dashboard.id)
            db.add(schedule)

        schedule.recipient_emails = list(dict.fromkeys(self._normalize_emails(payload.get("recipient_emails", []))))
        schedule.weekdays = [str(day).lower() for day in payload.get("weekdays", []) if str(day).strip()]
        schedule.send_time = str(payload.get("send_time") or "09:00")
        schedule.timezone = str(payload.get("timezone") or "Asia/Yakutsk")
        schedule.enabled = bool(payload.get("enabled", False))
        schedule.subject = str(payload.get("subject") or "Dashboard digest")
        db.commit()
        db.refresh(schedule)
        return schedule

    def delete_schedule(self, db: Session, dashboard: DashboardModel) -> bool:
        if dashboard.schedule is None:
            return False
        db.delete(dashboard.schedule)
        db.commit()
        return True

    def generate_dashboard_pdf(self, db: Session, dashboard: DashboardModel, dashboard_url: str) -> bytes:
        snapshots = self._collect_snapshots(db, dashboard)
        pages: list[list[str]] = []
        current: list[str] = []
        y = 792

        def ensure_space(lines: int) -> None:
            nonlocal current, y
            if y - lines * 14 < 72:
                self._finalize_page(pages, current)
                current = []
                self._start_page(current)
                y = 792

        self._start_page(current)
        self._draw_band(current, 0, 768, 595, 74, fill=(18, 20, 27))
        self._draw_text(current, 36, 807, dashboard.title, size=22, bold=True, color=(1, 1, 1))
        self._draw_text(
            current,
            36,
            786,
            f"Dashboard link: {dashboard_url}",
            size=9,
            color=(0.82, 0.84, 0.9),
        )
        if dashboard.description:
            self._draw_multiline(current, 36, 744, dashboard.description, width=520, size=10, color=(0.2, 0.2, 0.24))
            y = 708
        else:
            y = 724

        for snapshot in snapshots:
            ensure_space(10)
            self._draw_card(current, 32, y - 90, 531, 82)
            self._draw_text(current, 46, y - 26, snapshot.title, size=13, bold=True, color=(0.13, 0.15, 0.2))
            self._draw_text(
                current,
                46,
                y - 42,
                f"Type: {snapshot.kind}    Layout: x={snapshot.layout.get('x')}, y={snapshot.layout.get('y')}, w={snapshot.layout.get('w')}, h={snapshot.layout.get('h')}",
                size=8.5,
                color=(0.38, 0.4, 0.45),
            )
            if snapshot.kind == "text":
                self._draw_multiline(current, 46, y - 58, snapshot.body, width=500, size=9.2, color=(0.18, 0.2, 0.24))
            elif snapshot.preview_rows:
                self._draw_multiline(
                    current,
                    46,
                    y - 58,
                    self._format_preview(snapshot.columns, snapshot.preview_rows),
                    width=500,
                    size=8.8,
                    color=(0.18, 0.2, 0.24),
                )
            else:
                self._draw_text(current, 46, y - 58, "No preview data available.", size=9, color=(0.45, 0.45, 0.5))
            y -= 100

        self._draw_text(
            current,
            36,
            max(40, y - 6),
            "Generated without SQL source code in the export.",
            size=8,
            color=(0.42, 0.45, 0.5),
        )
        self._finalize_page(pages, current)
        return self._build_pdf(pages)

    def send_schedule_digest(self, db: Session, schedule: DashboardScheduleModel) -> bool:
        dashboard = schedule.dashboard
        if dashboard is None:
            return False
        if not schedule.enabled:
            return False
        if not schedule.recipient_emails:
            return False

        dashboard_url = f"/dashboards/{dashboard.slug or dashboard.id}"
        pdf_bytes = self.generate_dashboard_pdf(db, dashboard, dashboard_url)
        message = EmailMessage()
        message["Subject"] = schedule.subject
        message["From"] = settings.mail_from_address or settings.mail_smtp_user or "noreply@example.com"
        message["To"] = ", ".join(schedule.recipient_emails)
        message.set_content(
            f"Dashboard digest for {dashboard.title}\n\nOpen dashboard: {dashboard_url}\n"
        )
        message.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=f"{self._slugify(dashboard.title)}.pdf",
        )

        if not self._smtp_ready:
            logger.info("SMTP is not configured; skipping dashboard email for %s", dashboard.id)
            return False

        try:
            self._send_email(message)
            schedule.last_sent_at = datetime.utcnow()
            db.commit()
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to send dashboard digest: %s", exc)
            return False

    def dispatch_due_schedules(self) -> int:
        sent = 0
        with ServiceSessionLocal() as db:
            schedules = (
                db.query(DashboardScheduleModel)
                .filter(DashboardScheduleModel.enabled.is_(True))
                .all()
            )
            for schedule in schedules:
                if not self._is_schedule_due(schedule):
                    continue
                if self.send_schedule_digest(db, schedule):
                    sent += 1
        return sent

    def _collect_snapshots(self, db: Session, dashboard: DashboardModel) -> list[DashboardWidgetSnapshot]:
        snapshots: list[DashboardWidgetSnapshot] = []
        for dw in dashboard.dashboard_widgets:
            if dw.widget.deleted_at is not None:
                continue
            widget = dw.widget
            if widget.source_type == "text":
                snapshots.append(
                    DashboardWidgetSnapshot(
                        title=dw.title_override or widget.title,
                        kind="text",
                        layout=dw.layout or {},
                        body=widget.description or widget.sql_text or self.DEFAULT_TEXT_BODY,
                        preview_rows=[],
                        columns=[],
                    )
                )
                continue

            run = widget.runs[-1] if widget.runs else None
            if run is None and widget.sql_text.strip():
                run = self._execute_widget_preview(db, widget)

            if run is None:
                snapshots.append(
                    DashboardWidgetSnapshot(
                        title=dw.title_override or widget.title,
                        kind=widget.visualization_type,
                        layout=dw.layout or {},
                        body="No data available.",
                        preview_rows=[],
                        columns=[],
                    )
                )
                continue

            snapshots.append(
                DashboardWidgetSnapshot(
                    title=dw.title_override or widget.title,
                    kind=widget.visualization_type,
                    layout=dw.layout or {},
                    body="",
                    preview_rows=run.rows_preview_json or [],
                    columns=run.columns_json or [],
                )
            )
        return snapshots

    def _execute_widget_preview(self, db: Session, widget: WidgetModel) -> WidgetRunModel | None:
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
        with engine.begin() as connection:
            self._apply_read_only_guards(connection)
            df: pd.DataFrame = pd.read_sql_query(sa_text(widget.sql_text), connection)
        columns = [{"name": str(name), "type": str(df[name].dtype)} for name in df.columns]
        rows_full = json.loads(df.to_json(orient="records", date_format="iso"))
        rows_preview = rows_full[:20]
        return WidgetRunModel(
            widget_id=widget.id,
            status="completed",
            columns_json=columns,
            rows_preview_json=rows_preview,
            rows_preview_truncated=len(rows_full) > len(rows_preview),
            row_count=int(len(df.index)),
            execution_time_ms=0,
            error_text=None,
            finished_at=datetime.utcnow(),
        )

    def _apply_read_only_guards(self, connection: Any) -> None:
        dialect = connection.engine.dialect.name.lower()
        if dialect.startswith("postgres"):
            connection.exec_driver_sql("SET LOCAL default_transaction_read_only = on")
            connection.exec_driver_sql(f"SET LOCAL statement_timeout = {max(settings.query_timeout_seconds * 1000, 1000)}")
        elif dialect.startswith("sqlite"):
            connection.exec_driver_sql("PRAGMA query_only = ON")

    def _sanitize_layout(self, layout: dict[str, Any]) -> dict[str, int]:
        x = max(0, int(layout.get("x", 0)))
        y = max(0, int(layout.get("y", 0)))
        w = max(self.MIN_WIDGET_WIDTH, int(layout.get("w", 6)))
        h = max(self.MIN_WIDGET_HEIGHT, int(layout.get("h", 4)))
        w = min(self.GRID_COLUMNS, w)
        x = min(x, self.GRID_COLUMNS - w)
        return {"x": x, "y": y, "w": w, "h": h}

    def _layouts_overlap(self, left: dict[str, int], right: dict[str, int]) -> bool:
        return not (
            left["x"] + left["w"] <= right["x"]
            or right["x"] + right["w"] <= left["x"]
            or left["y"] + left["h"] <= right["y"]
            or right["y"] + right["h"] <= left["y"]
        )

    @property
    def _smtp_ready(self) -> bool:
        return bool(settings.mail_smtp_key and settings.mail_smtp_host and settings.mail_smtp_user)

    def _send_email(self, message: EmailMessage) -> None:
        host = settings.mail_smtp_host or ""
        port = int(settings.mail_smtp_port)
        user = settings.mail_smtp_user or ""
        key = settings.mail_smtp_key or ""
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=30) as client:
                client.login(user, key)
                client.send_message(message)
            return
        with smtplib.SMTP(host, port, timeout=30) as client:
            client.ehlo()
            if port != 25:
                client.starttls()
            client.login(user, key)
            client.send_message(message)

    def _normalize_emails(self, emails: Iterable[str]) -> list[str]:
        normalized: list[str] = []
        for email in emails:
            trimmed = str(email).strip()
            if trimmed and trimmed not in normalized:
                normalized.append(trimmed)
        return normalized

    def _is_schedule_due(self, schedule: DashboardScheduleModel) -> bool:
        if not schedule.enabled or schedule.dashboard is None:
            return False
        tz = ZoneInfo(schedule.timezone or "Asia/Yakutsk")
        now = datetime.now(tz)
        if schedule.last_sent_at is not None:
            last_sent = schedule.last_sent_at
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=ZoneInfo("UTC"))
            last_sent = last_sent.astimezone(tz)
            if last_sent.date() == now.date():
                return False
        weekdays = [day.lower() for day in (schedule.weekdays or [])]
        if weekdays:
            weekday_name = now.strftime("%a").lower()[:3]
            weekday_map = {
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
            normalized = {weekday_map.get(item, item[:3]) for item in weekdays}
            if weekday_name not in normalized:
                return False
        try:
            hh, mm = (int(part) for part in schedule.send_time.split(":", 1))
            due_time = time(hour=hh, minute=mm)
        except Exception:  # noqa: BLE001
            due_time = time(hour=9, minute=0)
        return now.time() >= due_time

    def _slugify(self, value: str) -> str:
        cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
        return cleaned or "dashboard"

    def _build_pdf(self, pages: list[list[str]]) -> bytes:
        objects: list[bytes] = []
        font_obj_id = 1
        content_ids = []
        page_ids = []
        pages_root_id = 2
        next_obj_id = 3

        for commands in pages:
            content = "\n".join(commands).encode("utf-8")
            content_id = next_obj_id
            next_obj_id += 1
            content_ids.append(content_id)
            objects.append(f"{content_id} 0 obj<< /Length {len(content)} >>stream\n".encode("utf-8") + content + b"\nendstream\nendobj\n")

        for content_id in content_ids:
            page_id = next_obj_id
            next_obj_id += 1
            page_ids.append(page_id)
            objects.append(
                (
                    f"{page_id} 0 obj<< /Type /Page /Parent {pages_root_id} 0 R /MediaBox [0 0 595 842] "
                    f"/Resources << /Font << /F1 {font_obj_id} 0 R >> >> /Contents {content_id} 0 R >>endobj\n"
                ).encode("utf-8")
            )

        pages_obj = (
            f"{pages_root_id} 0 obj<< /Type /Pages /Count {len(page_ids)} /Kids ["
            + " ".join(f"{page_id} 0 R" for page_id in page_ids)
            + "] >>endobj\n"
        ).encode("utf-8")
        catalog_id = next_obj_id
        next_obj_id += 1
        catalog = f"{catalog_id} 0 obj<< /Type /Catalog /Pages {pages_root_id} 0 R >>endobj\n".encode("utf-8")
        font = f"{font_obj_id} 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n".encode("utf-8")

        ordered_objects = [font, pages_obj, *objects, catalog]
        buffer = BytesIO()
        buffer.write(b"%PDF-1.4\n")
        offsets: list[int] = []
        for obj in ordered_objects:
            offsets.append(buffer.tell())
            buffer.write(obj)
        xref_pos = buffer.tell()
        buffer.write(f"xref\n0 {len(ordered_objects) + 1}\n".encode("utf-8"))
        buffer.write(b"0000000000 65535 f \n")
        for offset in offsets:
            buffer.write(f"{offset:010d} 00000 n \n".encode("utf-8"))
        buffer.write(
            (
                "trailer<< /Size "
                f"{len(ordered_objects) + 1}"
                f" /Root {catalog_id} 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
            ).encode("utf-8")
        )
        return buffer.getvalue()

    def _start_page(self, commands: list[str]) -> None:
        commands.extend([
            "BT /F1 12 Tf ET",
            "0 0 0 rg",
        ])

    def _finalize_page(self, pages: list[list[str]], current: list[str]) -> None:
        pages.append(current.copy())

    def _draw_band(self, commands: list[str], x: float, y: float, w: float, h: float, fill: tuple[float, float, float]) -> None:
        r, g, b = fill
        commands.append(f"{r} {g} {b} rg {x} {y} {w} {h} re f")

    def _draw_card(self, commands: list[str], x: float, y: float, w: float, h: float) -> None:
        commands.append("0.95 0.95 0.98 rg")
        commands.append(f"{x} {y} {w} {h} re f")
        commands.append("0.84 0.86 0.9 RG 1 w")
        commands.append(f"{x} {y} {w} {h} re S")

    def _draw_text(
        self,
        commands: list[str],
        x: float,
        y: float,
        text: str,
        size: float = 10,
        bold: bool = False,
        color: tuple[float, float, float] = (0, 0, 0),
    ) -> None:
        font = "/F1"
        r, g, b = color
        commands.append(f"BT {font} {size} Tf {r} {g} {b} rg {x} {y} Td ({self._escape(text)}) Tj ET")

    def _draw_multiline(
        self,
        commands: list[str],
        x: float,
        y: float,
        text: str,
        width: int,
        size: float = 10,
        color: tuple[float, float, float] = (0, 0, 0),
    ) -> None:
        current_y = y
        for paragraph in str(text).splitlines() or [""]:
            wrapped = textwrap.wrap(paragraph, width=width // max(int(size * 0.6), 1)) or [""]
            for line in wrapped:
                self._draw_text(commands, x, current_y, line, size=size, color=color)
                current_y -= max(size + 3, 11)

    def _format_preview(self, columns: list[dict[str, Any]], rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "No rows to preview."
        keys = [col["name"] for col in columns[:4]] if columns else list(rows[0].keys())[:4]
        lines = []
        for row in rows[:4]:
            parts = [f"{key}: {row.get(key)}" for key in keys]
            lines.append(" | ".join(parts))
        return "\n".join(lines)

    def _escape(self, text: str) -> str:
        ascii_text = self._transliterate(str(text))
        return ascii_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _transliterate(self, text: str) -> str:
        mapping = {
            "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
            "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
            "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh",
            "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
        }
        result: list[str] = []
        for char in text:
            lower = char.lower()
            if lower in mapping:
                translit = mapping[lower]
                result.append(translit.upper() if char.isupper() else translit)
            elif char.isascii():
                result.append(char)
            else:
                result.append(" ")
        return "".join(result)
