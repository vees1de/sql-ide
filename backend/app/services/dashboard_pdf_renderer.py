from __future__ import annotations

import textwrap
from io import BytesIO
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import DashboardModel
from app.services.dashboard_snapshot_service import DashboardSnapshotService
from app.services.dashboard_types import CHART_WIDGET_KINDS, ChartPoint, ChartSeries, DashboardWidgetSnapshot, WidgetKind


class DashboardPdfRenderer:
    GRID_COLUMNS = 12
    _PLOT_LEFT = 36
    _PLOT_BOTTOM = 24
    _PLOT_RIGHT = 14
    _PLOT_TOP = 14

    def __init__(self, snapshot_service: DashboardSnapshotService | None = None) -> None:
        self.snapshot_service = snapshot_service or DashboardSnapshotService()

    def generate_dashboard_pdf(self, db: Session, dashboard: DashboardModel, dashboard_url: str) -> bytes:
        snapshots = self.snapshot_service.collect_snapshots(db, dashboard)
        pages: list[list[str]] = []
        current: list[str] = []
        self._start_page(current)
        self._draw_pdf_header(current, dashboard, dashboard_url)

        cursor_y = 716
        for snapshot in snapshots:
            card_h = self._estimate_card_height(snapshot)
            if cursor_y - card_h < 48:
                self._finalize_page(pages, current)
                current = []
                self._start_page(current)
                cursor_y = 810
            self._draw_widget_card(current, snapshot, cursor_y)
            cursor_y -= card_h + 14

        if not snapshots:
            self._draw_text(current, 34, 680, "No widgets to display.", size=10, color=(0.5, 0.5, 0.5))

        self._finalize_page(pages, current)
        return self._build_pdf(pages)

    def slugify(self, value: str) -> str:
        normalized = self._transliterate(str(value))
        cleaned = "".join(ch.lower() if ch.isascii() and ch.isalnum() else "-" for ch in normalized)
        cleaned = "-".join(part for part in cleaned.split("-") if part)
        return cleaned or "dashboard"

    def _build_pdf(self, pages: list[list[str]]) -> bytes:
        objects: list[bytes] = []
        font_obj_id = 1
        bold_font_obj_id = 2
        content_ids: list[int] = []
        page_ids: list[int] = []
        pages_root_id = 3
        next_obj_id = 4

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
                    f"/Resources << /Font << /F1 {font_obj_id} 0 R /F2 {bold_font_obj_id} 0 R >> >> /Contents {content_id} 0 R >>endobj\n"
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
        bold_font = f"{bold_font_obj_id} 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>endobj\n".encode("utf-8")

        ordered_objects = [font, bold_font, pages_obj, *objects, catalog]
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
            "1 1 1 rg 0 0 595 842 re f",
            "BT /F1 12 Tf ET",
            "0 0 0 rg",
        ])

    def _finalize_page(self, pages: list[list[str]], current: list[str]) -> None:
        pages.append(current.copy())

    def _draw_band(self, commands: list[str], x: float, y: float, w: float, h: float, fill: tuple[float, float, float]) -> None:
        r, g, b = fill
        commands.append(f"{r:.4f} {g:.4f} {b:.4f} rg {x} {y} {w} {h} re f")

    def _draw_card(self, commands: list[str], x: float, y: float, w: float, h: float) -> None:
        commands.append(f"1 1 1 rg {x} {y} {w} {h} re f")
        commands.append(f"0.878 0.882 0.918 RG 0.8 w {x} {y} {w} {h} re S")

    def _draw_pdf_header(self, commands: list[str], dashboard: DashboardModel, dashboard_url: str) -> None:
        self._draw_band(commands, 0, 762, 595, 80, (0.071, 0.078, 0.106))
        self._draw_band(commands, 0, 762, 595, 2, (0.439, 0.231, 0.969))
        self._draw_text(commands, 34, 808, dashboard.title, size=20, bold=True, color=(0.95, 0.95, 1.0))
        self._draw_text(commands, 34, 784, f"Dashboard  ·  {dashboard_url}", size=8.5, color=(0.64, 0.67, 0.76))
        if dashboard.description:
            desc = dashboard.description if len(dashboard.description) <= 90 else dashboard.description[:87] + "..."
            self._draw_text(commands, 34, 771, desc, size=8.2, color=(0.55, 0.57, 0.65))

    def _draw_widget_card(self, commands: list[str], snapshot: DashboardWidgetSnapshot, top_y: float) -> None:
        card_h = self._estimate_card_height(snapshot)
        x = 32
        y = top_y - card_h
        w = 531
        header_h = 36

        self._draw_card(commands, x, y, w, card_h)
        self._draw_band(commands, x + 0.8, y + card_h - header_h, w - 1.6, header_h - 0.8, (0.957, 0.957, 0.973))
        self._draw_band(commands, x, y + card_h - header_h, 3, header_h, (0.439, 0.231, 0.969))

        self._draw_text(commands, x + 12, y + card_h - 22, snapshot.title, size=11, bold=True, color=(0.118, 0.137, 0.196))
        kind_label = snapshot.kind.value.replace("_", " ").title()
        self._draw_text(commands, x + 12, y + card_h - 32, kind_label, size=7.5, color=(0.439, 0.231, 0.969))

        content_top = y + card_h - header_h - 8
        if snapshot.kind == WidgetKind.TEXT:
            self._draw_multiline(commands, x + 12, content_top, snapshot.body, width=490, size=9.2, color=(0.18, 0.2, 0.24))
            return

        if not snapshot.preview_rows:
            self._draw_text(commands, x + 12, content_top - 12, "No data available.", size=9, color=(0.45, 0.45, 0.5))
            return

        if snapshot.kind == WidgetKind.METRIC:
            self._draw_metric(commands, x + 12, y + 12, w - 24, snapshot)
            return

        if snapshot.kind in CHART_WIDGET_KINDS:
            chart_h = card_h - header_h - 72
            self._draw_chart(commands, x + 12, y + 60, w - 24, max(80, chart_h), snapshot)
            self._draw_table_preview(commands, x + 12, y + 12, w - 24, snapshot)
            return

        self._draw_table_preview(commands, x + 12, y + 12, w - 24, snapshot)

    def _estimate_card_height(self, snapshot: DashboardWidgetSnapshot) -> int:
        header_h = 36
        if snapshot.kind == WidgetKind.TEXT:
            lines = max(3, len(textwrap.wrap(snapshot.body or "", width=70)) or 1)
            return max(100, header_h + 16 + lines * 13)
        if snapshot.kind == WidgetKind.METRIC:
            return header_h + 104
        if snapshot.kind in CHART_WIDGET_KINDS:
            row_count = min(len(snapshot.preview_rows), 4)
            table_h = 16 + row_count * 16 + 10 if row_count else 0
            if snapshot.kind == WidgetKind.PIE:
                return header_h + 154 + table_h + (18 if row_count else 10)
            chart_h = 152 if snapshot.preview_rows else 112
            return header_h + chart_h + table_h + (18 if row_count else 10)
        return header_h + 80

    def _draw_metric(self, commands: list[str], x: float, y: float, w: float, snapshot: DashboardWidgetSnapshot) -> None:
        rows = snapshot.preview_rows or []
        if not rows:
            self._draw_text(commands, x, y + 24, "No metric data available.", size=9, color=(0.45, 0.45, 0.5))
            return

        columns = [col.get("name") for col in snapshot.columns]
        metric_col = self._find_numeric_column(snapshot.columns, rows)
        metric_value = None
        if metric_col:
            metric_value = rows[0].get(metric_col)
        if metric_value is None and columns:
            metric_value = rows[0].get(columns[-1])
        self._draw_band(commands, x, y + 58, 4, 4, (0.439, 0.231, 0.969))
        self._draw_text(commands, x + 8, y + 60, metric_col or "Metric", size=8.5, color=(0.42, 0.44, 0.52))
        self._draw_text(commands, x, y + 28, self._format_value(metric_value), size=28, bold=True, color=(0.118, 0.137, 0.196))
        self._draw_text(commands, x, y + 10, self._metric_caption(snapshot), size=8, color=(0.46, 0.48, 0.54))

    def _draw_chart(self, commands: list[str], x: float, y: float, w: float, h: float, snapshot: DashboardWidgetSnapshot) -> None:
        chart = self._extract_chart_series(snapshot)
        if not chart.points:
            self._draw_text(commands, x, y + h / 2, "No chart data available.", size=9, color=(0.45, 0.45, 0.5))
            return

        if snapshot.kind == WidgetKind.PIE:
            self._draw_pie_chart(commands, x, y, w, h, chart)
            return

        self._draw_chart_frame(commands, x, y, w, h)
        if snapshot.kind in {WidgetKind.LINE, WidgetKind.AREA}:
            self._draw_line_chart(commands, x, y, w, h, chart, fill_area=snapshot.kind == WidgetKind.AREA)
        elif snapshot.kind in {WidgetKind.BAR, WidgetKind.STACKED_BAR}:
            self._draw_bar_chart(commands, x, y, w, h, chart)

    def _draw_chart_frame(self, commands: list[str], x: float, y: float, w: float, h: float) -> None:
        plot_x = x + 36
        plot_y = y + 24
        plot_w = w - 50
        plot_h = h - 38
        for i in range(1, 5):
            gy = plot_y + plot_h * i / 4
            self._draw_line(commands, plot_x, gy, plot_x + plot_w, gy, color=(0.902, 0.906, 0.925), width=0.5)
        self._draw_line(commands, plot_x, plot_y, plot_x, plot_y + plot_h, color=(0.780, 0.784, 0.816), width=0.8)
        self._draw_line(commands, plot_x, plot_y, plot_x + plot_w, plot_y, color=(0.780, 0.784, 0.816), width=0.8)

    def _plot_bounds(self, x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        return (
            x + self._PLOT_LEFT,
            y + self._PLOT_BOTTOM,
            w - self._PLOT_LEFT - self._PLOT_RIGHT,
            h - self._PLOT_BOTTOM - self._PLOT_TOP,
        )

    def _draw_line_chart(
        self,
        commands: list[str],
        x: float,
        y: float,
        w: float,
        h: float,
        chart: ChartSeries,
        fill_area: bool = False,
    ) -> None:
        plot_x, plot_y, plot_w, plot_h = self._plot_bounds(x, y, w, h)
        points = chart.points
        values = [point.y for point in points]
        minimum = min(values)
        maximum = max(values)
        span = max(maximum - minimum, 1e-9)
        xs: list[float] = []
        ys: list[float] = []
        for index, point in enumerate(points):
            px = plot_x + (plot_w * index / max(len(points) - 1, 1))
            py = plot_y + (plot_h * (point.y - minimum) / span)
            xs.append(px)
            ys.append(py)

        purple = (0.439, 0.231, 0.969)
        if fill_area:
            fill_points = [(plot_x, plot_y), *zip(xs, ys), (plot_x + plot_w, plot_y)]
            self._draw_polygon(commands, fill_points, fill=purple)

        for idx in range(len(xs) - 1):
            self._draw_line(commands, xs[idx], ys[idx], xs[idx + 1], ys[idx + 1], color=purple, width=1.8)
        for idx, (px, py) in enumerate(zip(xs, ys)):
            self._draw_square_marker(commands, px, py, 2.6, fill=purple)
            if len(points) <= 12:
                self._draw_text(commands, px - 10, py + 6, self._format_value(points[idx].y), size=6.5, color=(0.34, 0.26, 0.62))

        self._draw_chart_axis_labels(commands, chart, xs, plot_x, plot_y, plot_h)

    def _draw_bar_chart(self, commands: list[str], x: float, y: float, w: float, h: float, chart: ChartSeries) -> None:
        plot_x, plot_y, plot_w, plot_h = self._plot_bounds(x, y, w, h)
        points = chart.points
        values = [point.y for point in points]
        minimum = min(0.0, min(values))
        maximum = max(values)
        span = max(maximum - minimum, 1e-9)
        count = len(points)
        bar_gap = max(2.0, plot_w / max(count * 6, 1))
        bar_w = max(6.0, plot_w / max(count, 1) - bar_gap)
        for idx, point in enumerate(points):
            center_x = plot_x + plot_w * (idx + 0.5) / max(count, 1)
            bar_h = plot_h * (point.y - minimum) / span
            commands.append(f"0.439 0.231 0.969 rg {center_x - bar_w / 2:.2f} {plot_y:.2f} {bar_w:.2f} {bar_h:.2f} re f")
            if count <= 12:
                self._draw_text(commands, center_x - 10, plot_y + bar_h + 3, self._format_value(point.y), size=6.5, color=(0.34, 0.26, 0.62))
                self._draw_text(commands, center_x - 9, plot_y - 11, self._truncate_label(point.label), size=6.8, color=(0.42, 0.44, 0.50))
        self._draw_chart_axis_labels(commands, chart, [], plot_x, plot_y, plot_h)

    def _draw_pie_chart(self, commands: list[str], x: float, y: float, w: float, h: float, chart: ChartSeries) -> None:
        points = chart.points[:6]
        if not points:
            self._draw_text(commands, x, y + h / 2, "No pie data available.", size=9, color=(0.45, 0.45, 0.5))
            return

        total = sum(point.y for point in points) or 1.0
        cx = x + w * 0.28
        cy = y + h * 0.52
        radius = min(w * 0.27, h * 0.34)
        colors = [
            (0.44, 0.23, 0.97),
            (0.24, 0.58, 0.98),
            (0.93, 0.42, 0.33),
            (0.26, 0.72, 0.51),
            (0.97, 0.71, 0.22),
            (0.58, 0.37, 0.94),
        ]
        self._draw_text(commands, x, y + h - 8, "Share of total", size=7.4, color=(0.42, 0.45, 0.5))
        start = 0.0
        for idx, point in enumerate(points):
            sweep = 360.0 * point.y / total
            self._draw_wedge(commands, cx, cy, radius, start, start + sweep, colors[idx % len(colors)])
            start += sweep
        legend_x = x + w * 0.56
        legend_y = y + h - 22
        for idx, point in enumerate(points):
            color = colors[idx % len(colors)]
            self._draw_color_swatch(commands, legend_x, legend_y - idx * 15, color)
            pct = (point.y / total) * 100.0
            label = self._truncate_label(point.label)
            self._draw_text(
                commands,
                legend_x + 12,
                legend_y - idx * 15 + 1,
                f"{label}  {self._format_value(point.y)}  {pct:.0f}%",
                size=7.4,
                color=(0.22, 0.24, 0.28),
            )

    def _draw_table_preview(self, commands: list[str], x: float, y: float, w: float, snapshot: DashboardWidgetSnapshot) -> None:
        rows = snapshot.preview_rows[:4]
        columns = [col.get("name") for col in snapshot.columns[:4]] or list(rows[0].keys())[:4]
        if not rows or not columns:
            self._draw_text(commands, x, y + 8, "No tabular preview.", size=8.5, color=(0.45, 0.45, 0.5))
            return
        cell_w = w / max(len(columns), 1)
        row_h = 16
        header_y = y + row_h * len(rows)
        for idx, col in enumerate(columns):
            self._draw_band(commands, x + idx * cell_w, header_y, cell_w, row_h, (0.933, 0.937, 0.961))
            self._draw_text(commands, x + idx * cell_w + 4, header_y + 5, str(col), size=7.5, bold=True, color=(0.118, 0.137, 0.196))
        self._draw_line(commands, x, header_y, x + w, header_y, color=(0.878, 0.882, 0.918), width=0.5)
        for row_idx, row in enumerate(rows):
            row_y = header_y - (row_idx + 1) * row_h
            if row_idx % 2 == 1:
                self._draw_band(commands, x, row_y, w, row_h, (0.975, 0.976, 0.984))
            for col_idx, col in enumerate(columns):
                value = self._format_value(row.get(col))
                self._draw_text(commands, x + col_idx * cell_w + 4, row_y + 5, value, size=7.2, color=(0.26, 0.28, 0.32))
        self._draw_text(commands, x, y - 5, "Preview data", size=7.4, color=(0.439, 0.231, 0.969))

    def _draw_chart_axis_labels(
        self,
        commands: list[str],
        chart: ChartSeries,
        xs: list[float],
        plot_x: float,
        plot_y: float,
        plot_h: float,
    ) -> None:
        if not chart.points:
            return
        label_x = plot_x - self._PLOT_LEFT + 2
        self._draw_text(commands, label_x, plot_y + plot_h - 4, self._format_value(chart.maximum), size=6.5, color=(0.44, 0.46, 0.52))
        self._draw_text(commands, label_x, plot_y + 2, self._format_value(chart.minimum), size=6.5, color=(0.44, 0.46, 0.52))
        if xs:
            self._draw_text(commands, xs[0] - 8, plot_y - 11, self._truncate_label(chart.points[0].label), size=6.8, color=(0.42, 0.44, 0.50))
            self._draw_text(commands, xs[-1] - 8, plot_y - 11, self._truncate_label(chart.points[-1].label), size=6.8, color=(0.42, 0.44, 0.50))

    def _extract_chart_series(self, snapshot: DashboardWidgetSnapshot) -> ChartSeries:
        rows = snapshot.preview_rows or []
        x_key, y_key = self._guess_chart_axes(snapshot.columns, rows)
        points: list[ChartPoint] = []
        for row in rows[:20]:
            label = self._format_value(row.get(x_key)) if x_key else str(len(points) + 1)
            raw_value = row.get(y_key) if y_key else None
            value = self._coerce_number(raw_value)
            if value is None:
                continue
            points.append(ChartPoint(label=label, y=value, raw=raw_value))
        if not points and rows:
            for idx, row in enumerate(rows[:20]):
                value = self._first_numeric_in_row(row)
                if value is None:
                    continue
                points.append(ChartPoint(label=str(idx + 1), y=value, raw=value))
        return ChartSeries(
            points=points,
            x_key=x_key,
            y_key=y_key,
            minimum=min((point.y for point in points), default=0),
            maximum=max((point.y for point in points), default=0),
        )

    def _guess_chart_axes(self, columns: list[dict[str, Any]], rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
        if not rows:
            return None, None
        column_names = [str(col.get("name")) for col in columns] if columns else list(rows[0].keys())
        x_key = None
        y_key = None
        for name in column_names:
            sample = rows[0].get(name)
            if x_key is None and not self._looks_numeric(sample):
                x_key = name
            if y_key is None and self._looks_numeric(sample):
                y_key = name
        if y_key is None:
            for name in column_names:
                if name != x_key and self._looks_numeric(rows[0].get(name)):
                    y_key = name
                    break
        return x_key, y_key

    def _coerce_number(self, value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return float(int(value))
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        try:
            return float(text)
        except Exception:  # noqa: BLE001
            return None

    def _looks_numeric(self, value: Any) -> bool:
        return self._coerce_number(value) is not None

    def _find_numeric_column(self, columns: list[dict[str, Any]], rows: list[dict[str, Any]]) -> str | None:
        if not rows:
            return None
        candidates = [str(col.get("name")) for col in columns] if columns else list(rows[0].keys())
        for name in candidates:
            sample = rows[0].get(name)
            if self._looks_numeric(sample):
                return name
        for name in candidates:
            for row in rows[:5]:
                if self._looks_numeric(row.get(name)):
                    return name
        return None

    def _first_numeric_in_row(self, row: dict[str, Any]) -> float | None:
        for value in row.values():
            numeric = self._coerce_number(value)
            if numeric is not None:
                return numeric
        return None

    def _format_value(self, value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.2f}".rstrip("0").rstrip(".")
        if isinstance(value, int):
            return str(value)
        text = str(value)
        if len(text) > 26:
            text = text[:23] + "..."
        return text

    def _metric_caption(self, snapshot: DashboardWidgetSnapshot) -> str:
        rows = snapshot.preview_rows or []
        if len(rows) > 1:
            return f"Based on {len(rows)} rows"
        return "Single value metric"

    def _truncate_label(self, value: Any) -> str:
        text = self._format_value(value)
        return text if len(text) <= 12 else text[:9] + "..."

    def _draw_line(self, commands: list[str], x1: float, y1: float, x2: float, y2: float, color: tuple[float, float, float], width: float = 1.0) -> None:
        r, g, b = color
        commands.append(f"{r} {g} {b} RG {width} w {x1} {y1} m {x2} {y2} l S")

    def _draw_square_marker(self, commands: list[str], x: float, y: float, radius: float, fill: tuple[float, float, float]) -> None:
        r, g, b = fill
        commands.append(f"{r} {g} {b} rg")
        commands.append(f"{x - radius} {y - radius} {radius * 2} {radius * 2} re f")

    def _draw_polygon(self, commands: list[str], points: list[tuple[float, float]], fill: tuple[float, float, float]) -> None:
        if not points:
            return
        r, g, b = fill
        commands.append(f"{r} {g} {b} rg")
        commands.append(f"{points[0][0]} {points[0][1]} m")
        for px, py in points[1:]:
            commands.append(f"{px} {py} l")
        commands.append("h f")

    def _draw_wedge(
        self,
        commands: list[str],
        cx: float,
        cy: float,
        radius: float,
        start_deg: float,
        end_deg: float,
        color: tuple[float, float, float],
    ) -> None:
        import math

        r, g, b = color
        steps = max(3, int((end_deg - start_deg) / 12))
        commands.append(f"{r} {g} {b} rg")
        commands.append(f"{cx} {cy} m")
        for step in range(steps + 1):
            angle = math.radians(start_deg + (end_deg - start_deg) * step / steps)
            px = cx + math.cos(angle) * radius
            py = cy + math.sin(angle) * radius
            commands.append(f"{px} {py} l")
        commands.append("h f")

    def _draw_color_swatch(self, commands: list[str], x: float, y: float, color: tuple[float, float, float]) -> None:
        r, g, b = color
        commands.append(f"{r} {g} {b} rg {x} {y} 8 8 re f")

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
        font = "/F2" if bold else "/F1"
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
