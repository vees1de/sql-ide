from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.db.models import DashboardModel, DashboardWidgetModel, WidgetModel
from app.schemas.dashboards import (
    DashboardCreate,
    DashboardDetail,
    DashboardRead,
    DashboardScheduleRead,
    DashboardScheduleUpsert,
    DashboardUpdate,
    DashboardWidgetCreate,
    DashboardWidgetDetail,
    DashboardWidgetRead,
    DashboardWidgetUpdate,
)
from app.schemas.widgets import WidgetRead
from app.services.dashboard_service import DashboardService

router = APIRouter()
dashboard_service = DashboardService()


def _get_dashboard_or_404(db: Session, dashboard_id: str) -> DashboardModel:
    dashboard = (
        db.query(DashboardModel)
        .options(
            selectinload(DashboardModel.dashboard_widgets).selectinload(DashboardWidgetModel.widget).selectinload(WidgetModel.runs),
            selectinload(DashboardModel.schedule),
        )
        .filter(
            (DashboardModel.id == dashboard_id) | (DashboardModel.slug == dashboard_id),
            DashboardModel.deleted_at.is_(None),
        )
        .first()
    )
    if dashboard is None:
        raise HTTPException(status_code=404, detail="Dashboard not found.")
    return dashboard


def _get_dw_or_404(db: Session, dashboard_id: str, dw_id: str) -> DashboardWidgetModel:
    dw = db.query(DashboardWidgetModel).filter(
        DashboardWidgetModel.id == dw_id,
        DashboardWidgetModel.dashboard_id == dashboard_id,
    ).first()
    if dw is None:
        raise HTTPException(status_code=404, detail="Dashboard widget not found.")
    return dw


def _dw_to_detail(dw: DashboardWidgetModel) -> DashboardWidgetDetail:
    widget_read = WidgetRead.model_validate(dw.widget)
    dw_read = DashboardWidgetRead.model_validate(dw)
    return DashboardWidgetDetail(**dw_read.model_dump(mode="json"), widget=widget_read)


def _dashboard_to_detail(dashboard: DashboardModel) -> DashboardDetail:
    widgets = [_dw_to_detail(dw) for dw in dashboard.dashboard_widgets if dw.widget.deleted_at is None]
    schedule = DashboardScheduleRead.model_validate(dashboard.schedule) if dashboard.schedule is not None else None
    return DashboardDetail(
        **DashboardRead.model_validate(dashboard).model_dump(mode="json"),
        widgets=widgets,
        schedule=schedule,
    )


@router.get("/dashboards", response_model=list[DashboardRead])
def list_dashboards(
    include_hidden: bool = Query(False, description="Include hidden dashboards"),
    db: Session = Depends(get_db),
) -> list[DashboardRead]:
    query = db.query(DashboardModel).filter(DashboardModel.deleted_at.is_(None))
    if not include_hidden:
        query = query.filter(DashboardModel.is_hidden.is_(False))
    dashboards = query.order_by(DashboardModel.updated_at.desc()).all()
    return [DashboardRead.model_validate(d) for d in dashboards]


@router.post("/dashboards", response_model=DashboardDetail, status_code=201)
def create_dashboard(payload: DashboardCreate, db: Session = Depends(get_db)) -> DashboardDetail:
    dashboard = DashboardModel(
        title=payload.title,
        description=payload.description,
        is_public=payload.is_public,
        is_hidden=False,
    )
    db.add(dashboard)
    db.flush()

    for item in payload.widgets:
        widget = db.query(WidgetModel).filter(
            WidgetModel.id == item.widget_id,
            WidgetModel.deleted_at.is_(None),
        ).first()
        if widget is None:
            raise HTTPException(status_code=404, detail=f"Widget {item.widget_id} not found.")
        dw = DashboardWidgetModel(
            dashboard_id=dashboard.id,
            widget_id=item.widget_id,
            layout=item.layout.model_dump(),
            title_override=item.title_override,
            display_options=item.display_options,
        )
        db.add(dw)

    dashboard_service.ensure_default_text_widget(db, dashboard)
    db.commit()
    db.refresh(dashboard)
    return _dashboard_to_detail(dashboard)


@router.get("/dashboards/{dashboard_id}", response_model=DashboardDetail)
def get_dashboard(dashboard_id: str, db: Session = Depends(get_db)) -> DashboardDetail:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    if not any(dw.widget.source_type == "text" and dw.widget.deleted_at is None for dw in dashboard.dashboard_widgets):
        dashboard_service.ensure_default_text_widget(db, dashboard)
    dashboard_service.normalize_dashboard_layouts(db, dashboard)
    db.commit()
    db.refresh(dashboard)
    return _dashboard_to_detail(dashboard)


@router.patch("/dashboards/{dashboard_id}", response_model=DashboardDetail)
def update_dashboard(
    dashboard_id: str,
    payload: DashboardUpdate,
    db: Session = Depends(get_db),
) -> DashboardDetail:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    if payload.title is not None:
        dashboard.title = payload.title
    if payload.description is not None:
        dashboard.description = payload.description
    if payload.is_public is not None:
        dashboard.is_public = payload.is_public
    if payload.is_hidden is not None:
        dashboard.is_hidden = payload.is_hidden
    if payload.slug is not None:
        dashboard.slug = payload.slug or None
    db.commit()
    db.refresh(dashboard)
    return _dashboard_to_detail(dashboard)


@router.delete("/dashboards/{dashboard_id}", status_code=204)
def delete_dashboard(dashboard_id: str, db: Session = Depends(get_db)) -> Response:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    dashboard.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)


# --- Dashboard widgets ---

@router.get("/dashboards/{dashboard_id}/widgets", response_model=list[DashboardWidgetDetail])
def list_dashboard_widgets(dashboard_id: str, db: Session = Depends(get_db)) -> list[DashboardWidgetDetail]:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    return [_dw_to_detail(dw) for dw in dashboard.dashboard_widgets if dw.widget.deleted_at is None]


@router.post("/dashboards/{dashboard_id}/widgets", response_model=DashboardWidgetDetail, status_code=201)
def add_widget_to_dashboard(
    dashboard_id: str,
    payload: DashboardWidgetCreate,
    db: Session = Depends(get_db),
) -> DashboardWidgetDetail:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    widget = db.query(WidgetModel).filter(
        WidgetModel.id == payload.widget_id,
        WidgetModel.deleted_at.is_(None),
    ).first()
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found.")

    dw = DashboardWidgetModel(
        dashboard_id=dashboard_id,
        widget_id=payload.widget_id,
        layout=payload.layout.model_dump(),
        title_override=payload.title_override,
        display_options=payload.display_options,
    )
    db.add(dw)
    db.flush()
    dw.layout = dashboard_service.place_widget_layout(dashboard, dw.layout, exclude_dashboard_widget_id=dw.id)
    db.commit()
    db.refresh(dw)
    return _dw_to_detail(dw)


@router.get("/dashboards/{dashboard_id}/schedule", response_model=DashboardScheduleRead)
def get_dashboard_schedule(dashboard_id: str, db: Session = Depends(get_db)) -> DashboardScheduleRead:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    if dashboard.schedule is None:
        raise HTTPException(status_code=404, detail="Dashboard schedule not found.")
    return DashboardScheduleRead.model_validate(dashboard.schedule)


@router.patch("/dashboards/{dashboard_id}/schedule", response_model=DashboardScheduleRead)
def upsert_dashboard_schedule(
    dashboard_id: str,
    payload: DashboardScheduleUpsert,
    db: Session = Depends(get_db),
) -> DashboardScheduleRead:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    schedule = dashboard_service.upsert_schedule(db, dashboard, payload.model_dump(mode="json"))
    db.commit()
    db.refresh(schedule)
    return DashboardScheduleRead.model_validate(schedule)


@router.delete("/dashboards/{dashboard_id}/schedule", status_code=204)
def delete_dashboard_schedule(dashboard_id: str, db: Session = Depends(get_db)) -> Response:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    if not dashboard_service.delete_schedule(db, dashboard):
        raise HTTPException(status_code=404, detail="Dashboard schedule not found.")
    db.commit()
    return Response(status_code=204)


@router.get("/dashboards/{dashboard_id}/export/pdf")
def export_dashboard_pdf(dashboard_id: str, db: Session = Depends(get_db)) -> Response:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    dashboard_url = f"/dashboards/{dashboard.slug or dashboard.id}"
    pdf_bytes = dashboard_service.generate_dashboard_pdf(db, dashboard, dashboard_url)
    filename = dashboard_service.slugify(dashboard.slug or dashboard.title)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
    )


@router.patch("/dashboards/{dashboard_id}/widgets/{dw_id}", response_model=DashboardWidgetDetail)
def update_dashboard_widget(
    dashboard_id: str,
    dw_id: str,
    payload: DashboardWidgetUpdate,
    db: Session = Depends(get_db),
) -> DashboardWidgetDetail:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    dw = _get_dw_or_404(db, dashboard_id, dw_id)
    if payload.layout is not None:
        dw.layout = dashboard_service.place_widget_layout(
            dashboard,
            payload.layout.model_dump(),
            exclude_dashboard_widget_id=dw.id,
        )
    if payload.title_override is not None:
        dw.title_override = payload.title_override
    if payload.display_options is not None:
        dw.display_options = payload.display_options
    db.commit()
    db.refresh(dw)
    return _dw_to_detail(dw)


@router.delete("/dashboards/{dashboard_id}/widgets/{dw_id}", status_code=204)
def remove_widget_from_dashboard(
    dashboard_id: str,
    dw_id: str,
    db: Session = Depends(get_db),
) -> Response:
    _get_dashboard_or_404(db, dashboard_id)
    dw = _get_dw_or_404(db, dashboard_id, dw_id)
    db.delete(dw)
    db.commit()
    return Response(status_code=204)
