from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.notebook import (
    NotebookCellCreate,
    NotebookCellRunRequest,
    NotebookCellReorder,
    NotebookCellUpdate,
    NotebookCreate,
    NotebookDetail,
    NotebookRead,
    NotebookUpdate,
)
from app.schemas.query import CellRead, PromptRunRequest, PromptRunResponse, QueryRunRead
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


@router.post("/notebooks/{notebook_id}/cells", response_model=CellRead, status_code=201)
def create_cell(notebook_id: str, payload: NotebookCellCreate, db: Session = Depends(get_db)) -> CellRead:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    try:
        return notebook_service.create_cell(db, notebook, payload.type, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/notebooks/{notebook_id}/cells/{cell_id}", response_model=CellRead)
def update_cell(
    notebook_id: str,
    cell_id: str,
    payload: NotebookCellUpdate,
    db: Session = Depends(get_db),
) -> CellRead:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    cell = notebook_service.get_cell(db, notebook_id, cell_id)
    if cell is None:
        raise HTTPException(status_code=404, detail="Cell not found.")
    try:
        return notebook_service.update_cell(db, notebook, cell, payload.content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/notebooks/{notebook_id}/cells/{cell_id}/run", response_model=PromptRunResponse, status_code=201)
def run_cell(
    notebook_id: str,
    cell_id: str,
    payload: NotebookCellRunRequest | None = None,
    db: Session = Depends(get_db),
) -> PromptRunResponse:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    cell = notebook_service.get_cell(db, notebook_id, cell_id)
    if cell is None:
        raise HTTPException(status_code=404, detail="Cell not found.")
    if cell.query_run_id is not None or cell.type not in notebook_service.input_cell_types:
        raise HTTPException(status_code=400, detail="Only editable prompt/sql cells can be executed.")

    if cell.type == "prompt" and not str(cell.content.get("text", "")).strip():
        raise HTTPException(status_code=400, detail="Prompt cell is empty.")
    if cell.type == "sql" and not str(cell.content.get("sql", "")).strip():
        raise HTTPException(status_code=400, detail="SQL cell is empty.")

    if payload and payload.query_mode and cell.type in notebook_service.input_cell_types:
        notebook_service.set_input_cell_query_mode(db, notebook, cell, payload.query_mode, commit=False)
    if payload and payload.llm_model_alias and cell.type in notebook_service.input_cell_types:
        notebook_service.set_input_cell_model_alias(db, notebook, cell, payload.llm_model_alias, commit=False)

    notebook_service.delete_runs_for_input_cell(db, notebook, cell)
    db.refresh(notebook)

    query_mode = notebook_service.resolve_input_cell_query_mode(cell)
    llm_model_alias = notebook_service.resolve_input_cell_model_alias(cell)

    if cell.type == "prompt":
        prompt = str(cell.content.get("text", "")).strip()
        response = orchestration_service.run_prompt(
            db,
            notebook,
            prompt,
            existing_prompt_cell=cell,
            query_mode=query_mode,
            llm_model_alias=llm_model_alias,
        )
    else:
        response = orchestration_service.run_sql_cell(
            db,
            notebook,
            cell,
            query_mode=query_mode,
            llm_model_alias=llm_model_alias,
        )

    db.refresh(notebook)
    notebook_service.reorder_blocks(db, notebook)
    db.commit()
    return response


@router.post("/notebooks/{notebook_id}/cells/{cell_id}/format-sql", response_model=CellRead)
def format_sql_cell(notebook_id: str, cell_id: str, db: Session = Depends(get_db)) -> CellRead:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    cell = notebook_service.get_cell(db, notebook_id, cell_id)
    if cell is None:
        raise HTTPException(status_code=404, detail="Cell not found.")
    if cell.query_run_id is not None or cell.type != "sql":
        raise HTTPException(status_code=400, detail="Only editable SQL cells can be formatted.")

    formatted_sql = orchestration_service.validation_agent.format_sql(
        str(cell.content.get("sql", "")),
        orchestration_service._resolve_dialect(db, notebook),
    )
    return notebook_service.update_cell(db, notebook, cell, {"sql": formatted_sql})


@router.post("/notebooks/{notebook_id}/cells/reorder", response_model=NotebookDetail)
def reorder_cells(
    notebook_id: str,
    payload: NotebookCellReorder,
    db: Session = Depends(get_db),
) -> NotebookDetail:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    try:
        notebook_service.reorder_blocks(db, notebook, payload.ordered_cell_ids)
        db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.refresh(notebook)
    notebook.cells.sort(key=lambda item: item.position)
    notebook.query_runs.sort(key=lambda item: item.created_at)
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
    response = orchestration_service.run_prompt(
        db,
        notebook,
        payload.prompt,
        query_mode=payload.query_mode,
        llm_model_alias=payload.llm_model_alias,
    )
    db.refresh(notebook)
    notebook_service.reorder_blocks(db, notebook)
    db.commit()
    return response


@router.post("/notebooks/{notebook_id}/run-all", response_model=list[PromptRunResponse])
def run_all(notebook_id: str, db: Session = Depends(get_db)) -> list[PromptRunResponse]:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    responses = orchestration_service.rerun_notebook(db, notebook)
    db.refresh(notebook)
    notebook_service.reorder_blocks(db, notebook)
    db.commit()
    return responses


@router.get("/notebooks/{notebook_id}/history", response_model=list[QueryRunRead])
def notebook_history(notebook_id: str, db: Session = Depends(get_db)) -> list[QueryRunRead]:
    notebook = notebook_service.get_notebook(db, notebook_id)
    if notebook is None:
        raise HTTPException(status_code=404, detail="Notebook not found.")
    return notebook_service.list_history(db, notebook_id)
