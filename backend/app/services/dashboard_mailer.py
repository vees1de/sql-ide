from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.db.models import DashboardModel, DashboardScheduleModel


logger = logging.getLogger(__name__)


class DashboardMailer:
    @property
    def smtp_ready(self) -> bool:
        return bool(settings.mail_smtp_key and settings.mail_smtp_host and settings.mail_smtp_user)

    def send_dashboard_digest(
        self,
        schedule: DashboardScheduleModel,
        dashboard: DashboardModel,
        pdf_bytes: bytes,
        dashboard_url: str,
        filename: str,
    ) -> bool:
        if not self.smtp_ready:
            logger.info("SMTP is not configured; skipping dashboard email for %s", dashboard.id)
            return False

        message = EmailMessage()
        message["Subject"] = schedule.subject
        message["From"] = settings.mail_from_address or settings.mail_smtp_user or "noreply@example.com"
        message["To"] = ", ".join(schedule.recipient_emails)
        message.set_content(f"Dashboard digest for {dashboard.title}\n\nOpen dashboard: {dashboard_url}\n")
        message.add_attachment(
            pdf_bytes,
            maintype="application",
            subtype="pdf",
            filename=f"{filename}.pdf",
        )

        try:
            self._send_email(message)
            return True
        except smtplib.SMTPException as exc:
            logger.warning("Failed to send dashboard digest via SMTP: %s", exc)
            return False

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
