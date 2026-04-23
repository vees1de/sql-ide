from __future__ import annotations

import logging
from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import DashboardModel, DashboardScheduleModel
from app.services.dashboard_types import MOSCOW_TZ, normalize_weekday


logger = logging.getLogger(__name__)


class DashboardScheduleService:
    def upsert_schedule(
        self,
        db: Session,
        dashboard: DashboardModel,
        payload: dict[str, object],
    ) -> DashboardScheduleModel:
        schedule = dashboard.schedule
        if schedule is None:
            schedule = DashboardScheduleModel(dashboard_id=dashboard.id)
            db.add(schedule)

        schedule.recipient_emails = list(dict.fromkeys(self._normalize_emails(payload.get("recipient_emails", []))))
        schedule.weekdays = [normalize_weekday(day) for day in payload.get("weekdays", []) if str(day).strip()]
        schedule.send_time = str(payload.get("send_time") or "09:00")
        timezone = str(payload.get("timezone") or MOSCOW_TZ)
        ZoneInfo(timezone)
        schedule.timezone = timezone
        schedule.enabled = bool(payload.get("enabled", False))
        schedule.subject = str(payload.get("subject") or "Dashboard digest")
        db.flush()
        return schedule

    def delete_schedule(self, db: Session, dashboard: DashboardModel) -> bool:
        if dashboard.schedule is None:
            return False
        db.delete(dashboard.schedule)
        db.flush()
        return True

    def is_schedule_due(self, schedule: DashboardScheduleModel) -> bool:
        if not schedule.enabled or schedule.dashboard is None:
            return False
        tz_name = schedule.timezone or MOSCOW_TZ
        try:
            tz = ZoneInfo(tz_name)
        except Exception:  # noqa: BLE001
            logger.warning("Invalid dashboard schedule timezone %s; falling back to %s", tz_name, MOSCOW_TZ)
            tz = ZoneInfo(MOSCOW_TZ)
        now = datetime.now(tz)
        if schedule.last_sent_at is not None:
            last_sent = schedule.last_sent_at
            if last_sent.tzinfo is None:
                last_sent = last_sent.replace(tzinfo=timezone.utc)
            last_sent = last_sent.astimezone(tz)
            if last_sent.date() == now.date():
                return False
        weekdays = [normalize_weekday(day) for day in (schedule.weekdays or [])]
        if weekdays and now.strftime("%a").lower()[:3] not in set(weekdays):
            return False
        try:
            hh, mm = (int(part) for part in schedule.send_time.split(":", 1))
            due_time = time(hour=hh, minute=mm)
        except Exception:  # noqa: BLE001
            due_time = time(hour=9, minute=0)
        return now.time() >= due_time

    def _normalize_emails(self, emails: object) -> list[str]:
        normalized: list[str] = []
        for email in emails if isinstance(emails, list) else []:
            trimmed = str(email).strip()
            if trimmed and trimmed not in normalized:
                normalized.append(trimmed)
        return normalized
