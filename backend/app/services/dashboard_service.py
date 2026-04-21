from __future__ import annotations

import logging
from typing import Any
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import DashboardModel, DashboardScheduleModel
from app.db.session import ServiceSessionLocal
from app.services.dashboard_layout_service import DashboardLayoutService
from app.services.dashboard_mailer import DashboardMailer
from app.services.dashboard_pdf_renderer import DashboardPdfRenderer
from app.services.dashboard_schedule_service import DashboardScheduleService
from app.services.dashboard_snapshot_service import DashboardSnapshotService


logger = logging.getLogger(__name__)


class DashboardService:
    def __init__(
        self,
        layout_service: DashboardLayoutService | None = None,
        snapshot_service: DashboardSnapshotService | None = None,
        pdf_renderer: DashboardPdfRenderer | None = None,
        mailer: DashboardMailer | None = None,
        schedule_service: DashboardScheduleService | None = None,
    ) -> None:
        self.layout_service = layout_service or DashboardLayoutService()
        self.snapshot_service = snapshot_service or DashboardSnapshotService()
        self.pdf_renderer = pdf_renderer or DashboardPdfRenderer(self.snapshot_service)
        self.mailer = mailer or DashboardMailer()
        self.schedule_service = schedule_service or DashboardScheduleService()

    def ensure_default_text_widget(self, db: Session, dashboard: DashboardModel):
        return self.layout_service.ensure_default_text_widget(db, dashboard)

    def place_widget_layout(
        self,
        dashboard: DashboardModel,
        desired_layout: dict[str, object],
        exclude_dashboard_widget_id: str | None = None,
    ) -> dict[str, int]:
        return self.layout_service.place_widget_layout(dashboard, desired_layout, exclude_dashboard_widget_id)

    def normalize_dashboard_layouts(self, db: Session, dashboard: DashboardModel) -> bool:
        return self.layout_service.normalize_dashboard_layouts(db, dashboard)

    def upsert_schedule(
        self,
        db: Session,
        dashboard: DashboardModel,
        payload: dict[str, object],
    ):
        return self.schedule_service.upsert_schedule(db, dashboard, payload)

    def delete_schedule(self, db: Session, dashboard: DashboardModel) -> bool:
        return self.schedule_service.delete_schedule(db, dashboard)

    def generate_dashboard_pdf(self, db: Session, dashboard: DashboardModel, dashboard_url: str) -> bytes:
        return self.pdf_renderer.generate_dashboard_pdf(db, dashboard, dashboard_url)

    def send_schedule_digest(self, db: Session, schedule: DashboardScheduleModel) -> bool:
        dashboard = schedule.dashboard
        if dashboard is None or not schedule.enabled or not schedule.recipient_emails:
            return False

        dashboard_url = f"/dashboards/{dashboard.slug or dashboard.id}"
        pdf_bytes = self.generate_dashboard_pdf(db, dashboard, dashboard_url)
        filename = self.slugify(dashboard.title)
        if not self.mailer.send_dashboard_digest(schedule, dashboard, pdf_bytes, dashboard_url, filename):
            return False

        schedule.last_sent_at = datetime.now(UTC)
        return True

    def dispatch_due_schedules(self) -> int:
        sent = 0
        with ServiceSessionLocal() as db:
            schedules = (
                db.execute(
                    select(DashboardScheduleModel)
                    .options(selectinload(DashboardScheduleModel.dashboard))
                    .where(DashboardScheduleModel.enabled.is_(True))
                )
                .scalars()
                .all()
            )
            for schedule in schedules:
                try:
                    if not self.is_schedule_due(schedule):
                        continue
                    if self.send_schedule_digest(db, schedule):
                        db.commit()
                        sent += 1
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to dispatch dashboard schedule %s: %s", schedule.id, exc)
        return sent

    def collect_snapshots(self, db: Session, dashboard: DashboardModel):
        return self.snapshot_service.collect_snapshots(db, dashboard)

    def execute_widget_preview(self, db: Session, widget: Any):
        return self.snapshot_service.execute_widget_preview(db, widget)

    def is_schedule_due(self, schedule: DashboardScheduleModel) -> bool:
        return self.schedule_service.is_schedule_due(schedule)

    def slugify(self, value: str) -> str:
        return self.pdf_renderer.slugify(value)

    def _slugify(self, value: str) -> str:
        return self.slugify(value)

    def _is_schedule_due(self, schedule: DashboardScheduleModel) -> bool:
        return self.is_schedule_due(schedule)
