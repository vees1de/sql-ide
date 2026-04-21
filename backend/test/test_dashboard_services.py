from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd

from app.db.models import DashboardModel, DashboardScheduleModel, WidgetModel
from app.services.dashboard_layout_service import DashboardLayoutService
from app.services.dashboard_schedule_service import DashboardScheduleService
from app.services.dashboard_service import DashboardService
from app.services.dashboard_snapshot_service import DashboardSnapshotService
from app.services.dashboard_types import GridLayout


class _NoCommitDB:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.deleted: list[object] = []
        self.flushed = False

    def add(self, obj: object) -> None:
        self.added.append(obj)

    def delete(self, obj: object) -> None:
        self.deleted.append(obj)

    def flush(self) -> None:
        self.flushed = True


def test_layout_service_sanitizes_and_detects_overlap() -> None:
    service = DashboardLayoutService()
    layout = service._sanitize_layout({"x": -5, "y": 2, "w": 99, "h": 1})
    assert layout == GridLayout(x=0, y=2, w=12, h=3)
    assert service._layouts_overlap(GridLayout(0, 0, 4, 4), GridLayout(3, 3, 4, 4))
    assert not service._layouts_overlap(GridLayout(0, 0, 4, 4), GridLayout(4, 0, 4, 4))


def test_schedule_service_upsert_does_not_commit() -> None:
    db = _NoCommitDB()
    dashboard = DashboardModel(title="Demo dashboard")
    service = DashboardScheduleService()

    schedule = service.upsert_schedule(
        db,  # type: ignore[arg-type]
        dashboard,
        {
            "recipient_emails": ["a@example.com", "a@example.com", "b@example.com"],
            "weekdays": ["Monday", "wed"],
            "send_time": "08:30",
            "timezone": "UTC",
            "enabled": True,
            "subject": "Daily digest",
        },
    )

    assert db.flushed is True
    assert schedule.enabled is True
    assert schedule.recipient_emails == ["a@example.com", "b@example.com"]
    assert schedule.weekdays == ["mon", "wed"]
    assert schedule.timezone == "UTC"


def test_schedule_service_delete_does_not_commit() -> None:
    db = _NoCommitDB()
    dashboard = DashboardModel(title="Demo dashboard")
    schedule = DashboardScheduleModel(dashboard=dashboard)
    dashboard.schedule = schedule
    service = DashboardScheduleService()

    deleted = service.delete_schedule(db, dashboard)  # type: ignore[arg-type]

    assert deleted is True
    assert db.flushed is True
    assert db.deleted == [schedule]


def test_snapshot_service_limited_preview(monkeypatch) -> None:
    service = DashboardSnapshotService()
    widget = WidgetModel(
        title="Orders",
        source_type="sql",
        sql_text="select * from orders",
        visualization_type="line",
        database_connection_id="conn-1",
    )
    db = SimpleNamespace()

    class _Conn:
        def __init__(self) -> None:
            self.engine = SimpleNamespace(dialect=SimpleNamespace(name="sqlite"))

        def exec_driver_sql(self, *_args, **_kwargs) -> None:
            return None

    class _Engine:
        def begin(self):
            class _Ctx:
                def __enter__(self_inner):
                    return _Conn()

                def __exit__(self_inner, exc_type, exc, tb):
                    return False

            return _Ctx()

    monkeypatch.setattr("app.services.dashboard_snapshot_service.resolve_engine", lambda _db, _conn_id: _Engine())

    def _read_sql_query(sql, connection):  # noqa: ANN001
        assert "LIMIT 21" in str(sql)
        return pd.DataFrame(
            {
                "label": [f"row-{idx}" for idx in range(25)],
                "value": list(range(25)),
            }
        )

    monkeypatch.setattr("app.services.dashboard_snapshot_service.pd.read_sql_query", _read_sql_query)

    result = service.execute_widget_preview(db, widget)

    assert result is not None
    assert result.row_count == 25
    assert len(result.rows_preview) == 20
    assert result.rows_preview_truncated is True
    assert result.columns[1]["name"] == "value"


def test_dashboard_service_send_schedule_digest_sets_last_sent_at(monkeypatch) -> None:
    dashboard = DashboardModel(title="Finance", slug="finance")
    schedule = DashboardScheduleModel(
        dashboard=dashboard,
        enabled=True,
        recipient_emails=["ops@example.com"],
        subject="Digest",
    )
    dashboard.schedule = schedule

    class _Mailer:
        def send_dashboard_digest(self, *args, **kwargs):  # noqa: ANN001, ANN002
            return True

    class _PdfRenderer:
        def generate_dashboard_pdf(self, *args, **kwargs):  # noqa: ANN001, ANN002
            return b"%PDF-1.4"

        def slugify(self, value: str) -> str:
            return value.lower()

    service = DashboardService(
        layout_service=DashboardLayoutService(),
        snapshot_service=DashboardSnapshotService(),
        pdf_renderer=_PdfRenderer(),  # type: ignore[arg-type]
        mailer=_Mailer(),  # type: ignore[arg-type]
        schedule_service=DashboardScheduleService(),
    )

    result = service.send_schedule_digest(object(), schedule)  # type: ignore[arg-type]

    assert result is True
    assert schedule.last_sent_at is not None
    assert schedule.last_sent_at.tzinfo == UTC
    assert schedule.last_sent_at <= datetime.now(UTC)
