from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from app.core.config import normalize_llm_model_alias
from app.db.models import CellModel, NotebookModel, QueryRunModel, utcnow
from app.schemas.notebook import NotebookCreate, NotebookUpdate
from app.schemas.query import QueryMode, normalize_query_mode


class NotebookService:
    input_cell_types = {"prompt", "sql"}

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

    def get_cell(self, db: Session, notebook_id: str, cell_id: str) -> CellModel | None:
        return (
            db.query(CellModel)
            .filter(CellModel.notebook_id == notebook_id, CellModel.id == cell_id)
            .first()
        )

    def list_input_cells(self, notebook: NotebookModel) -> list[CellModel]:
        return sorted(
            (
                cell
                for cell in notebook.cells
                if cell.query_run_id is None and cell.type in self.input_cell_types
            ),
            key=lambda item: item.position,
        )

    def create_cell(
        self,
        db: Session,
        notebook: NotebookModel,
        cell_type: str,
        content: dict,
    ) -> CellModel:
        if cell_type not in self.input_cell_types:
            raise ValueError("Only prompt and sql notebook cells can be created.")

        cell = CellModel(
            notebook_id=notebook.id,
            type=cell_type,
            position=self.next_cell_position(notebook),
            content=self._normalize_input_content(cell_type, content),
        )
        db.add(cell)
        db.flush()
        notebook.cells.append(cell)
        self.touch_notebook(notebook)
        db.commit()
        db.refresh(cell)
        return cell

    def update_cell(
        self,
        db: Session,
        notebook: NotebookModel,
        cell: CellModel,
        content: dict,
    ) -> CellModel:
        if cell.query_run_id is not None or cell.type not in self.input_cell_types:
            raise ValueError("Only editable prompt/sql cells can be updated.")

        cell.content = self._normalize_input_content(cell.type, content)
        self.touch_notebook(notebook)
        db.commit()
        db.refresh(cell)
        return cell

    def resolve_input_cell_query_mode(self, cell: CellModel) -> QueryMode:
        if not isinstance(cell.content, dict):
            return "fast"
        raw_mode = cell.content.get("query_mode")
        if raw_mode is None:
            raw_mode = cell.content.get("queryMode")
        return normalize_query_mode(str(raw_mode) if raw_mode is not None else None)

    def resolve_input_cell_model_alias(self, cell: CellModel) -> str:
        if not isinstance(cell.content, dict):
            return normalize_llm_model_alias(None)
        raw_alias = cell.content.get("llm_model_alias")
        if raw_alias is None:
            raw_alias = cell.content.get("llmModelAlias")
        return normalize_llm_model_alias(str(raw_alias) if raw_alias is not None else None)

    def set_input_cell_query_mode(
        self,
        db: Session,
        notebook: NotebookModel,
        cell: CellModel,
        query_mode: QueryMode,
        *,
        commit: bool = True,
    ) -> CellModel:
        if cell.query_run_id is not None or cell.type not in self.input_cell_types:
            raise ValueError("Only editable prompt/sql cells can be updated.")

        normalized = self._normalize_input_content(cell.type, {**dict(cell.content or {}), "query_mode": query_mode})
        cell.content = normalized
        self.touch_notebook(notebook)
        db.flush()
        if commit:
            db.commit()
            db.refresh(cell)
        return cell

    def set_input_cell_model_alias(
        self,
        db: Session,
        notebook: NotebookModel,
        cell: CellModel,
        llm_model_alias: str,
        *,
        commit: bool = True,
    ) -> CellModel:
        if cell.query_run_id is not None or cell.type not in self.input_cell_types:
            raise ValueError("Only editable prompt/sql cells can be updated.")

        normalized = self._normalize_input_content(
            cell.type,
            {**dict(cell.content or {}), "llm_model_alias": llm_model_alias},
        )
        cell.content = normalized
        self.touch_notebook(notebook)
        db.flush()
        if commit:
            db.commit()
            db.refresh(cell)
        return cell

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
        input_cells = self.list_input_cells(notebook)
        input_ids = {cell.id for cell in input_cells}
        for cell in list(notebook.cells):
            if cell.id not in input_ids:
                db.delete(cell)
        for query_run in list(notebook.query_runs):
            db.delete(query_run)
        for position, input_cell in enumerate(input_cells, start=1):
            input_cell.position = position
        self.touch_notebook(notebook)
        db.flush()

    def delete_runs_for_input_cell(self, db: Session, notebook: NotebookModel, cell: CellModel) -> None:
        run_ids = {query_run.id for query_run in notebook.query_runs if query_run.prompt_cell_id == cell.id}
        if not run_ids:
            return

        for generated_cell in list(notebook.cells):
            if generated_cell.query_run_id in run_ids:
                db.delete(generated_cell)
        for query_run in list(notebook.query_runs):
            if query_run.id in run_ids:
                db.delete(query_run)
        self.touch_notebook(notebook)
        db.flush()

    def reorder_blocks(
        self,
        db: Session,
        notebook: NotebookModel,
        ordered_input_cell_ids: list[str] | None = None,
    ) -> None:
        input_cells = self.list_input_cells(notebook)
        input_cell_map = {cell.id: cell for cell in input_cells}
        current_ids = {cell.id for cell in input_cells}

        if ordered_input_cell_ids is None:
            ordered_input_cells = input_cells
        else:
            requested_ids = [cell_id for cell_id in ordered_input_cell_ids if cell_id in input_cell_map]
            if set(requested_ids) != current_ids or len(requested_ids) != len(current_ids):
                raise ValueError("Cell order must include every editable prompt/sql cell exactly once.")
            ordered_input_cells = [input_cell_map[cell_id] for cell_id in requested_ids]

        latest_run_by_source: dict[str, QueryRunModel] = {}
        for query_run in sorted(notebook.query_runs, key=lambda item: item.created_at):
            latest_run_by_source[query_run.prompt_cell_id] = query_run

        assigned_ids: set[str] = set()
        position = 1

        for input_cell in ordered_input_cells:
            input_cell.position = position
            position += 1
            assigned_ids.add(input_cell.id)

            latest_run = latest_run_by_source.get(input_cell.id)
            if latest_run is None:
                continue

            generated_cells = sorted(
                (
                    cell
                    for cell in notebook.cells
                    if cell.query_run_id == latest_run.id
                ),
                key=lambda item: item.position,
            )
            for generated_cell in generated_cells:
                generated_cell.position = position
                position += 1
                assigned_ids.add(generated_cell.id)

        leftovers = sorted(
            (cell for cell in notebook.cells if cell.id not in assigned_ids),
            key=lambda item: (item.position, item.created_at),
        )
        for leftover in leftovers:
            leftover.position = position
            position += 1

        self.touch_notebook(notebook)
        db.flush()

    def touch_notebook(self, notebook: NotebookModel) -> None:
        notebook.updated_at = utcnow()

    def _normalize_input_content(self, cell_type: str, content: dict) -> dict:
        query_mode = normalize_query_mode(
            str(content.get("query_mode") if content.get("query_mode") is not None else content.get("queryMode"))
            if content.get("query_mode") is not None or content.get("queryMode") is not None
            else None
        )
        llm_model_alias = normalize_llm_model_alias(
            str(
                content.get("llm_model_alias")
                if content.get("llm_model_alias") is not None
                else content.get("llmModelAlias")
            )
            if content.get("llm_model_alias") is not None or content.get("llmModelAlias") is not None
            else None
        )
        if cell_type == "prompt":
            prompt_text = str(content.get("text", content.get("prompt", "")) or "").strip()
            return {
                "text": prompt_text,
                "query_mode": query_mode,
                "llm_model_alias": llm_model_alias,
            }

        return {
            "sql": str(content.get("sql", "") or "").strip(),
            "query_mode": query_mode,
            "llm_model_alias": llm_model_alias,
        }
