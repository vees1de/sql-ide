from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import QueryExecutionModel
from app.services.example_service import ExampleService

router = APIRouter()
_svc = ExampleService()


class ExampleOut(BaseModel):
    id: str
    database_id: str
    prompt: str
    sql: str
    source: str
    quality_score: float
    use_count: int
    active: bool
    created_at: str


class ExampleCreate(BaseModel):
    prompt: str
    sql: str
    source: str = "manual"
    quality_score: float = 1.0


class FeedbackIn(BaseModel):
    feedback: str  # "good" | "bad"
    edited_sql: str | None = None


@router.get("/databases/{database_id}/examples", response_model=list[ExampleOut])
def list_examples(database_id: str, db: Session = Depends(get_db)) -> Any:
    return [
        ExampleOut(
            id=ex.id,
            database_id=ex.database_id,
            prompt=ex.prompt,
            sql=ex.sql,
            source=ex.source,
            quality_score=ex.quality_score,
            use_count=ex.use_count,
            active=ex.active,
            created_at=ex.created_at.isoformat(),
        )
        for ex in _svc.list_examples(db, database_id)
    ]


@router.post("/databases/{database_id}/examples", response_model=ExampleOut, status_code=201)
def create_example(database_id: str, body: ExampleCreate, db: Session = Depends(get_db)) -> Any:
    ex = _svc.save_example(
        db,
        database_id,
        body.prompt,
        body.sql,
        source=body.source,
        quality_score=body.quality_score,
    )
    return ExampleOut(
        id=ex.id,
        database_id=ex.database_id,
        prompt=ex.prompt,
        sql=ex.sql,
        source=ex.source,
        quality_score=ex.quality_score,
        use_count=ex.use_count,
        active=ex.active,
        created_at=ex.created_at.isoformat(),
    )


@router.delete("/databases/{database_id}/examples/{example_id}", status_code=204)
def delete_example(database_id: str, example_id: str, db: Session = Depends(get_db)) -> None:
    deleted = _svc.delete_example(db, example_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Example not found")


@router.post(
    "/chat/sessions/{session_id}/executions/{execution_id}/feedback",
    status_code=204,
)
def execution_feedback(
    session_id: str,
    execution_id: str,
    body: FeedbackIn,
    db: Session = Depends(get_db),
) -> None:
    execution = (
        db.query(QueryExecutionModel)
        .filter(
            QueryExecutionModel.id == execution_id,
            QueryExecutionModel.session_id == session_id,
        )
        .first()
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")

    execution.feedback = body.feedback
    if body.edited_sql:
        execution.user_edited_sql = body.edited_sql

    db.add(execution)
    db.commit()

    # Propagate feedback to the matching example (matched by sql_text + session database)
    from app.db.models import ChatSessionModel, QueryExampleModel
    session = db.query(ChatSessionModel).filter(ChatSessionModel.id == session_id).first()
    if session:
        ex = (
            db.query(QueryExampleModel)
            .filter(
                QueryExampleModel.database_id == session.database_connection_id,
                QueryExampleModel.sql == (body.edited_sql or execution.sql_text),
            )
            .first()
        )
        if ex:
            _svc.record_feedback(db, ex.id, body.feedback)
        elif body.edited_sql and body.feedback == "good":
            # Save the edited version as a new high-quality example
            from app.services.example_service import _tokenize
            from app.db.models import ChatMessageModel
            msgs = db.query(ChatMessageModel).filter(
                ChatMessageModel.session_id == session_id,
                ChatMessageModel.role == "user",
            ).order_by(ChatMessageModel.created_at.desc()).first()
            user_prompt = msgs.text if msgs else ""
            if user_prompt:
                _svc.save_example(
                    db,
                    session.database_connection_id,
                    user_prompt,
                    body.edited_sql,
                    source="edited",
                    quality_score=1.5,
                )
