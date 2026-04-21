from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.analytics import (
    AnalyticsQueryRequest,
    AnalyticsResponse,
    ClarificationRequest,
    DashboardRecommendationRequest,
    DashboardRecommendationResponse,
    MetadataBundleResponse,
    NotebookSaveRequest,
)
from app.schemas.notebook import NotebookRead
from app.schemas.query import ClarificationAnswerRecord
from app.schemas.notebook import NotebookCreate
from app.services.analytics_agent_service import AnalyticsAgentService
from app.services.notebook_service import NotebookService


router = APIRouter()
analytics_service = AnalyticsAgentService()
notebook_service = NotebookService()


@router.post("/query", response_model=AnalyticsResponse)
def query(payload: AnalyticsQueryRequest, db: Session = Depends(get_db)) -> AnalyticsResponse:
    return analytics_service.run_query(db, payload)


@router.post("/clarify", response_model=AnalyticsResponse)
def clarify(payload: ClarificationRequest, db: Session = Depends(get_db)) -> AnalyticsResponse:
    request = AnalyticsQueryRequest(query=payload.query, context=payload.context)
    answers = [
        ClarificationAnswerRecord(
            clarification_id=payload.clarification_id or answer.id,
            ambiguity_type=answer.id,
            option_id=answer.selected_option_id,
            text_answer=answer.text_answer,
        )
        for answer in payload.answers
    ]
    return analytics_service.run_query(db, request, answers=answers)


@router.get("/metadata", response_model=MetadataBundleResponse)
def metadata(db: Session = Depends(get_db)) -> MetadataBundleResponse:
    bundle = analytics_service.list_metadata(db)
    return MetadataBundleResponse.model_validate(bundle)



@router.post("/dashboards/recommend", response_model=DashboardRecommendationResponse)
def recommend_dashboards(
    payload: DashboardRecommendationRequest,
    db: Session = Depends(get_db),
) -> DashboardRecommendationResponse:
    return analytics_service.recommend_dashboards(
        payload.intent,
        payload.user_context,
        payload.dashboards,
    )


@router.post("/notebook/save", response_model=NotebookRead)
def save_notebook(payload: NotebookSaveRequest, db: Session = Depends(get_db)) -> NotebookRead:
    if payload.notebook_id:
        notebook = notebook_service.get_notebook(db, payload.notebook_id)
        if notebook is None:
            raise HTTPException(status_code=404, detail="Notebook not found.")
        if payload.title is not None:
            notebook.title = payload.title.strip() or notebook.title
        if payload.database_id is not None:
            notebook.database_id = payload.database_id
        if payload.status is not None:
            notebook.status = payload.status
        db.commit()
        db.refresh(notebook)
        return NotebookRead.model_validate(notebook)

    if not payload.workspace_id or not payload.title or not payload.database_id:
        raise HTTPException(
            status_code=400,
            detail="workspace_id, title, and database_id are required when creating a notebook.",
        )
    notebook = notebook_service.create_notebook(
        db,
        NotebookCreate(
            workspace_id=payload.workspace_id,
            title=payload.title,
            database_id=payload.database_id,
        ),
    )
    return NotebookRead.model_validate(notebook)
