from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import WidgetModel, WidgetRunModel
from app.schemas.widgets import WidgetCreate, WidgetDetail, WidgetRead, WidgetRunRead, WidgetUpdate

router = APIRouter()


def _get_widget_or_404(db: Session, widget_id: str) -> WidgetModel:
    widget = db.query(WidgetModel).filter(
        WidgetModel.id == widget_id,
        WidgetModel.deleted_at.is_(None),
    ).first()
    if widget is None:
        raise HTTPException(status_code=404, detail="Widget not found.")
    return widget


def _widget_to_detail(widget: WidgetModel) -> WidgetDetail:
    last_run = widget.runs[-1] if widget.runs else None
    last_run_read = None
    if last_run:
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


@router.get("/widgets", response_model=list[WidgetRead])
def list_widgets(db: Session = Depends(get_db)) -> list[WidgetRead]:
    widgets = db.query(WidgetModel).filter(WidgetModel.deleted_at.is_(None)).order_by(WidgetModel.updated_at.desc()).all()
    return [WidgetRead.model_validate(w) for w in widgets]


@router.post("/widgets", response_model=WidgetDetail, status_code=201)
def create_widget(payload: WidgetCreate, db: Session = Depends(get_db)) -> WidgetDetail:
    widget = WidgetModel(
        title=payload.title,
        description=payload.description,
        source_type=payload.source_type,
        source_query_run_id=payload.source_query_run_id,
        sql_text=payload.sql_text,
        visualization_type=payload.visualization_type,
        visualization_config=payload.visualization_config,
        refresh_policy=payload.refresh_policy,
        is_public=payload.is_public,
        database_connection_id=payload.database_connection_id,
    )
    db.add(widget)
    db.commit()
    db.refresh(widget)
    return _widget_to_detail(widget)


@router.get("/widgets/{widget_id}", response_model=WidgetDetail)
def get_widget(widget_id: str, db: Session = Depends(get_db)) -> WidgetDetail:
    widget = _get_widget_or_404(db, widget_id)
    return _widget_to_detail(widget)


@router.patch("/widgets/{widget_id}", response_model=WidgetDetail)
def update_widget(widget_id: str, payload: WidgetUpdate, db: Session = Depends(get_db)) -> WidgetDetail:
    widget = _get_widget_or_404(db, widget_id)
    if payload.title is not None:
        widget.title = payload.title
    if payload.description is not None:
        widget.description = payload.description
    if payload.sql_text is not None:
        widget.sql_text = payload.sql_text
    if payload.visualization_type is not None:
        widget.visualization_type = payload.visualization_type
    if payload.visualization_config is not None:
        widget.visualization_config = payload.visualization_config
    if payload.refresh_policy is not None:
        widget.refresh_policy = payload.refresh_policy
    if payload.is_public is not None:
        widget.is_public = payload.is_public
    db.commit()
    db.refresh(widget)
    return _widget_to_detail(widget)


@router.delete("/widgets/{widget_id}", status_code=204)
def delete_widget(widget_id: str, db: Session = Depends(get_db)) -> Response:
    widget = _get_widget_or_404(db, widget_id)
    widget.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)


@router.post("/widgets/{widget_id}/run", response_model=WidgetDetail, status_code=201)
def run_widget(widget_id: str, db: Session = Depends(get_db)) -> WidgetDetail:
    """Execute the widget SQL and cache the result."""
    import json
    import time

    import pandas as pd
    from sqlalchemy import text as sa_text

    from app.db.models import DatabaseConnectionModel
    from app.services.chat_execution_service import ChatExecutionService
    from app.services.database_resolution import resolve_engine

    widget = _get_widget_or_404(db, widget_id)
    if widget.source_type == "text":
        run = WidgetRunModel(
            widget_id=widget.id,
            status="completed",
            columns_json=[{"name": "text", "type": "text"}],
            rows_preview_json=[{"text": widget.description or widget.sql_text or ""}],
            rows_preview_truncated=False,
            row_count=1,
            execution_time_ms=0,
            error_text=None,
            finished_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        widget.result_schema = {"columns": run.columns_json}
        db.commit()
        db.refresh(widget)
        return _widget_to_detail(widget)

    if not widget.sql_text.strip():
        raise HTTPException(status_code=400, detail="Widget has no SQL to execute.")

    run = WidgetRunModel(widget_id=widget.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        conn_id = widget.database_connection_id
        if not conn_id:
            first = db.query(DatabaseConnectionModel).first()
            conn_id = first.id if first else None
        if not conn_id:
            raise ValueError("No database connection available for this widget.")

        engine = resolve_engine(db, conn_id)
        svc = ChatExecutionService()
        started = time.perf_counter()
        with engine.begin() as connection:
            df: pd.DataFrame = pd.read_sql_query(sa_text(widget.sql_text), connection)
        elapsed = int((time.perf_counter() - started) * 1000)

        columns = svc._serialize_columns(df)
        rows_full = json.loads(df.to_json(orient="records", date_format="iso"))
        rows_preview, truncated = svc._serialize_preview(rows_full)

        run.status = "completed"
        run.columns_json = columns
        run.rows_preview_json = rows_preview
        run.rows_preview_truncated = truncated
        run.row_count = int(len(df.index))
        run.execution_time_ms = elapsed
        run.finished_at = datetime.now(timezone.utc)

        # Cache schema on widget
        widget.result_schema = {"columns": columns}
    except Exception as exc:
        run.status = "error"
        run.error_text = str(exc)
        run.finished_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(widget)
    return _widget_to_detail(widget)
