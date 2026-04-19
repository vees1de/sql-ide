from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.notebook import NotebookCreate, NotebookDetail, NotebookRead, NotebookUpdate
from app.schemas.query import PromptRunRequest, PromptRunResponse, QueryRunRead
from app.services.notebook_service import NotebookService
from app.services.orchestration_service import QueryOrchestrationService


router = APIRouter()
notebook_service = NotebookService()
orchestration_service = QueryOrchestrationService()


@router.get("/notebooks", response_model=list[NotebookRead])
def list_notebooks(db: Session = Depends(get_db)) -> list[NotebookRead]:
    return notebook_service.list_notebooks(db)


@router.post("/notebooks", response_model=NotebookRead, status_code=201)
def create_notebook(payload: NotebookCreate, db: Session = Depends(get_db)) -> NotebookRead:
    return notebook_service.create_notebook(db, payload)


@router.get("/notebooks/{notebook_id}", response_model=NotebookDetail)
def get_notebook(notebook_id: str, db: Session = Depends(get_db)) -> NotebookDetail:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    notebook.cells.sort(key=lambda item: item.position)
    notebook.query_runs.sort(key=lambda item: item.created_at)
    return notebook


@router.patch("/notebooks/{notebook_id}", response_model=NotebookRead)
def update_notebook(notebook_id: str, payload: NotebookUpdate, db: Session = Depends(get_db)) -> NotebookRead:
    notebook = notebook_service.update_notebook(db, notebook_id, payload)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    return notebook


@router.delete("/notebooks/{notebook_id}", status_code=204)
def delete_notebook(notebook_id: str, db: Session = Depends(get_db)) -> Response:
    deleted = notebook_service.delete_notebook(db, notebook_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    return Response(status_code=204)


@router.post("/notebooks/{notebook_id}/prompt-runs", response_model=PromptRunResponse, status_code=201)
def run_prompt(notebook_id: str, payload: PromptRunRequest, db: Session = Depends(get_db)) -> PromptRunResponse:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    return orchestration_service.run_prompt(db, notebook, payload.prompt)


@router.post("/notebooks/{notebook_id}/run-all", response_model=list[PromptRunResponse])
def run_all(notebook_id: str, db: Session = Depends(get_db)) -> list[PromptRunResponse]:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    return orchestration_service.rerun_notebook(db, notebook)


@router.get("/notebooks/{notebook_id}/history", response_model=list[QueryRunRead])
def notebook_history(notebook_id: str, db: Session = Depends(get_db)) -> list[QueryRunRead]:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    return notebook_service.list_history(db, notebook_id)
