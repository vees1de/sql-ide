from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import DashboardModel, DashboardWidgetModel, WidgetModel
from app.schemas.dashboards import (
    DashboardCreate,
    DashboardDetail,
    DashboardRead,
    DashboardUpdate,
    DashboardWidgetCreate,
    DashboardWidgetDetail,
    DashboardWidgetRead,
    DashboardWidgetUpdate,
)
from app.schemas.widgets import WidgetRead

router = APIRouter()


def _get_dashboard_or_404(db: Session, dashboard_id: str) -> DashboardModel:
    dashboard = db.query(DashboardModel).filter(
        (DashboardModel.id == dashboard_id) | (DashboardModel.slug == dashboard_id),
        DashboardModel.deleted_at.is_(None),
    ).first()
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
    return DashboardDetail(**DashboardRead.model_validate(dashboard).model_dump(mode="json"), widgets=widgets)


@router.get("/dashboards", response_model=list[DashboardRead])
def list_dashboards(db: Session = Depends(get_db)) -> list[DashboardRead]:
    dashboards = (
        db.query(DashboardModel)
        .filter(DashboardModel.deleted_at.is_(None))
        .order_by(DashboardModel.updated_at.desc())
        .all()
    )
    return [DashboardRead.model_validate(d) for d in dashboards]


@router.post("/dashboards", response_model=DashboardDetail, status_code=201)
def create_dashboard(payload: DashboardCreate, db: Session = Depends(get_db)) -> DashboardDetail:
    dashboard = DashboardModel(
        title=payload.title,
        description=payload.description,
        is_public=payload.is_public,
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

    db.commit()
    db.refresh(dashboard)
    return _dashboard_to_detail(dashboard)


@router.get("/dashboards/{dashboard_id}", response_model=DashboardDetail)
def get_dashboard(dashboard_id: str, db: Session = Depends(get_db)) -> DashboardDetail:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
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
    if payload.slug is not None:
        dashboard.slug = payload.slug or None
    db.commit()
    db.refresh(dashboard)
    return _dashboard_to_detail(dashboard)


@router.delete("/dashboards/{dashboard_id}", status_code=204)
def delete_dashboard(dashboard_id: str, db: Session = Depends(get_db)) -> Response:
    dashboard = _get_dashboard_or_404(db, dashboard_id)
    dashboard.deleted_at = datetime.utcnow()
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
    _get_dashboard_or_404(db, dashboard_id)
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
    db.commit()
    db.refresh(dw)
    return _dw_to_detail(dw)


@router.patch("/dashboards/{dashboard_id}/widgets/{dw_id}", response_model=DashboardWidgetDetail)
def update_dashboard_widget(
    dashboard_id: str,
    dw_id: str,
    payload: DashboardWidgetUpdate,
    db: Session = Depends(get_db),
) -> DashboardWidgetDetail:
    _get_dashboard_or_404(db, dashboard_id)
    dw = _get_dw_or_404(db, dashboard_id, dw_id)
    if payload.layout is not None:
        dw.layout = payload.layout.model_dump()
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
