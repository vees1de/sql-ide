from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.db.models import CellModel, NotebookModel, QueryRunModel
from app.schemas.notebook import NotebookCreate, NotebookUpdate


class NotebookService:
    def list_notebooks(self, db: Session) -> list[NotebookModel]:
        return db.query(NotebookModel).order_by(NotebookModel.updated_at.desc()).all()

    def create_notebook(self, db: Session, payload: NotebookCreate) -> NotebookModel:
        notebook = NotebookModel(
            workspace_id=payload.workspace_id,
            title=payload.title,
            database_id=payload.database_id,
            status="draft",
        )
        db.add(notebook)
        db.commit()
        db.refresh(notebook)
        return notebook

    def get_notebook(self, db: Session, notebook_id: str) -> NotebookModel | None:
        return (
            db.query(NotebookModel)
            .options(selectinload(NotebookModel.cells), selectinload(NotebookModel.query_runs))
            .filter(NotebookModel.id == notebook_id)
            .first()
        )

    def update_notebook(self, db: Session, notebook_id: str, payload: NotebookUpdate) -> NotebookModel | None:
        notebook = db.query(NotebookModel).filter(NotebookModel.id == notebook_id).first()
        if notebook is None:
            return None
        if payload.title is not None:
            notebook.title = payload.title
        if payload.status is not None:
            notebook.status = payload.status
        db.commit()
        db.refresh(notebook)
        return notebook

    def delete_notebook(self, db: Session, notebook_id: str) -> bool:
        notebook = db.query(NotebookModel).filter(NotebookModel.id == notebook_id).first()
        if notebook is None:
            return False
        db.delete(notebook)
        db.commit()
        return True

    def list_history(self, db: Session, notebook_id: str) -> list[QueryRunModel]:
        return (
            db.query(QueryRunModel)
            .filter(QueryRunModel.notebook_id == notebook_id)
            .order_by(QueryRunModel.created_at.asc())
            .all()
        )

    def get_last_successful_intent(self, db: Session, notebook_id: str) -> dict | None:
        latest_run = (
            db.query(QueryRunModel)
            .filter(QueryRunModel.notebook_id == notebook_id, QueryRunModel.status == "success")
            .order_by(QueryRunModel.created_at.desc())
            .first()
        )
        if latest_run is None:
            return None
        return latest_run.agent_trace.get("intent")

    def next_cell_position(self, notebook: NotebookModel) -> int:
        if not notebook.cells:
            return 1
        return max(cell.position for cell in notebook.cells) + 1

    def delete_generated_runs(self, db: Session, notebook: NotebookModel) -> None:
        prompt_cells = [cell for cell in notebook.cells if cell.type == "prompt"]
        for cell in list(notebook.cells):
            if cell.type != "prompt":
                db.delete(cell)
        for query_run in list(notebook.query_runs):
            db.delete(query_run)
        for position, prompt_cell in enumerate(sorted(prompt_cells, key=lambda item: item.position), start=1):
            prompt_cell.position = position
        db.flush()
