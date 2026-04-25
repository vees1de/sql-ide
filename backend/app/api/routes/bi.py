from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db
from app.db.models import DashboardModel, DashboardWidgetModel, DatasetModel, WidgetModel
from app.schemas.bi import (
    ChartPreviewRequest,
    ChartPreviewResponse,
    ChartRecommendationRead,
    ChartSaveRequest,
    ChartSaveResponse,
    ChartValidationRequest,
    ChartValidationResponse,
    DatasetPreviewResponse,
    DatasetRead,
    DatasetUpdate,
    QuickDashboardRequest,
    QuickDashboardResponse,
)
from app.schemas.dashboards import DashboardDetail, DashboardRead, DashboardScheduleRead, DashboardWidgetDetail, DashboardWidgetRead
from app.schemas.widgets import WidgetDetail, WidgetRead, WidgetRunRead
from app.services.bi_service import BiService

router = APIRouter()
bi_service = BiService()


def _http_error(exc: Exception) -> HTTPException:
    message = str(exc) or exc.__class__.__name__
    if "not found" in message.lower():
        return HTTPException(status_code=404, detail=message)
    return HTTPException(status_code=400, detail=message)


def _widget_to_detail(widget: WidgetModel) -> WidgetDetail:
    last_run = widget.runs[-1] if widget.runs else None
    last_run_read = None
    if last_run is not None:
        last_run_read = WidgetRunRead.model_validate(
            {
                "id": last_run.id,
                "widget_id": last_run.widget_id,
                "status": last_run.status,
                "columns": last_run.columns_json,
                "rows_preview": last_run.rows_preview_json,
                "rows_preview_truncated": last_run.rows_preview_truncated,
                "row_count": last_run.row_count,
                "execution_time_ms": last_run.execution_time_ms,
                "error_text": last_run.error_text,
                "started_at": last_run.started_at,
                "finished_at": last_run.finished_at,
            }
        )
    return WidgetDetail.model_validate(
        {**WidgetRead.model_validate(widget).model_dump(mode="json"), "last_run": last_run_read}
    )


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


@router.get("/datasets", response_model=list[DatasetRead])
def list_datasets(db: Session = Depends(get_db)) -> list[DatasetRead]:
    return bi_service.list_datasets(db)


@router.get("/datasets/{dataset_id}", response_model=DatasetRead)
def get_dataset(dataset_id: str, db: Session = Depends(get_db)) -> DatasetRead:
    try:
        dataset = bi_service.get_dataset_or_raise(db, dataset_id)
        return bi_service.dataset_to_read(dataset)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.patch("/datasets/{dataset_id}", response_model=DatasetRead)
def update_dataset(dataset_id: str, payload: DatasetUpdate, db: Session = Depends(get_db)) -> DatasetRead:
    try:
        dataset = bi_service.get_dataset_or_raise(db, dataset_id)
        if payload.name is not None:
            dataset.name = payload.name.strip()
        if payload.refresh_policy is not None:
            dataset.refresh_policy = payload.refresh_policy
        db.add(dataset)
        db.commit()
        db.refresh(dataset)
        return bi_service.dataset_to_read(dataset)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: str, db: Session = Depends(get_db)) -> Response:
    try:
        dataset = bi_service.get_dataset_or_raise(db, dataset_id)
        active_widgets = [widget for widget in (dataset.widgets or []) if widget.deleted_at is None]
        if active_widgets:
            raise ValueError("Dataset is used by saved charts. Delete charts first.")
        db.delete(dataset)
        db.commit()
        return Response(status_code=204)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.get("/datasets/{dataset_id}/preview", response_model=DatasetPreviewResponse)
def preview_dataset(dataset_id: str, db: Session = Depends(get_db)) -> DatasetPreviewResponse:
    try:
        dataset = bi_service.get_dataset_or_raise(db, dataset_id)
        return DatasetPreviewResponse(
            dataset=bi_service.dataset_to_read(dataset),
            columns=list(dataset.columns_schema or []),
            rows=list(dataset.preview_rows or []),
            row_count=int(dataset.row_count or 0),
            rows_preview_truncated=False,
        )
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.post("/datasets/{dataset_id}/refresh", response_model=DatasetRead)
def refresh_dataset(dataset_id: str, db: Session = Depends(get_db)) -> DatasetRead:
    try:
        dataset = bi_service.get_dataset_or_raise(db, dataset_id)
        refreshed = bi_service.refresh_dataset(db, dataset)
        return bi_service.dataset_to_read(refreshed)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.get("/datasets/{dataset_id}/chart-recommendations", response_model=list[ChartRecommendationRead])
def recommend_dataset_charts(dataset_id: str, db: Session = Depends(get_db)) -> list[ChartRecommendationRead]:
    try:
        dataset = bi_service.get_dataset_or_raise(db, dataset_id)
        return bi_service.recommend_charts(dataset)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.post("/charts/validate", response_model=ChartValidationResponse)
def validate_chart(payload: ChartValidationRequest, db: Session = Depends(get_db)) -> ChartValidationResponse:
    try:
        dataset = bi_service.get_dataset_or_raise(db, payload.dataset_id)
        return bi_service.validate_chart_spec(dataset, payload.chart_spec, payload.filters)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.post("/charts/preview", response_model=ChartPreviewResponse)
def preview_chart(payload: ChartPreviewRequest, db: Session = Depends(get_db)) -> ChartPreviewResponse:
    try:
        dataset = bi_service.get_dataset_or_raise(db, payload.dataset_id)
        return bi_service.preview_chart(db, dataset, payload.chart_spec, payload.filters)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.post("/charts", response_model=ChartSaveResponse, status_code=201)
def save_chart(payload: ChartSaveRequest, db: Session = Depends(get_db)) -> ChartSaveResponse:
    try:
        dataset = bi_service.get_dataset_or_raise(db, payload.dataset_id)
        widget, preview = bi_service.save_chart_widget(
            db,
            dataset,
            payload.chart_spec,
            title=payload.title,
            description=payload.description,
            run_immediately=payload.run_immediately,
        )
        widget = (
            db.query(WidgetModel)
            .options(selectinload(WidgetModel.runs))
            .filter(WidgetModel.id == widget.id)
            .first()
            or widget
        )
        return ChartSaveResponse(widget=_widget_to_detail(widget), preview=preview)
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc


@router.post("/datasets/{dataset_id}/quick-dashboard", response_model=QuickDashboardResponse, status_code=201)
def create_quick_dashboard(dataset_id: str, payload: QuickDashboardRequest, db: Session = Depends(get_db)) -> QuickDashboardResponse:
    try:
        dataset = bi_service.get_dataset_or_raise(db, dataset_id)
        dashboard, widgets, recommendations = bi_service.create_dashboard_from_recommendations(
            db,
            dataset,
            title=payload.title,
            max_widgets=payload.max_widgets,
        )
        dashboard = (
            db.query(DashboardModel)
            .options(
                selectinload(DashboardModel.dashboard_widgets)
                .selectinload(DashboardWidgetModel.widget)
                .selectinload(WidgetModel.runs),
                selectinload(DashboardModel.schedule),
            )
            .filter(DashboardModel.id == dashboard.id)
            .first()
            or dashboard
        )
        hydrated_widgets = (
            db.query(WidgetModel)
            .options(selectinload(WidgetModel.runs))
            .filter(WidgetModel.id.in_([widget.id for widget in widgets]))
            .all()
        )
        return QuickDashboardResponse(
            dashboard=_dashboard_to_detail(dashboard),
            widgets=[_widget_to_detail(widget) for widget in hydrated_widgets],
            recommendations=recommendations,
        )
    except Exception as exc:  # noqa: BLE001
        raise _http_error(exc) from exc
