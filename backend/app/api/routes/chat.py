from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import ChatMessageModel, ChatSessionModel, QueryExecutionModel
from app.schemas.chat import (
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionRead,
    ChatSessionUpdate,
    ExecuteRequest,
    ExecuteResponse,
    QueryExecutionRead,
    SendMessageResponse,
    SqlDraftUpdate,
)
from app.schemas.workspace import DatabaseDescriptor
from app.services.chat_execution_service import ChatExecutionService
from app.services.chat_service import ChatService, SqlDraftConflictError
from app.services.chat_sql_adapter import ChatSqlAdapter


router = APIRouter()
chat_service = ChatService()
chat_adapter = ChatSqlAdapter()
chat_execution_service = ChatExecutionService()

_SESSION_BUSY: set[str] = set()
_SESSION_BUSY_LOCK = threading.Lock()


def _try_mark_session_busy(session_id: str) -> bool:
    with _SESSION_BUSY_LOCK:
        if session_id in _SESSION_BUSY:
            return False
        _SESSION_BUSY.add(session_id)
        return True


def _release_session_busy(session_id: str) -> None:
    with _SESSION_BUSY_LOCK:
        _SESSION_BUSY.discard(session_id)


def _session_to_read(session: ChatSessionModel) -> ChatSessionRead:
    return ChatSessionRead.model_validate(session)


def _message_to_read(message: ChatMessageModel) -> ChatMessageRead:
    return ChatMessageRead.model_validate(message)


def _execution_to_read(execution: QueryExecutionModel) -> QueryExecutionRead:
    payload = {
        "id": execution.id,
        "session_id": execution.session_id,
        "sql_text": execution.sql_text,
        "columns": execution.columns_json,
        "rows_preview": execution.rows_preview_json,
        "rows_preview_truncated": execution.rows_preview_truncated,
        "row_count": execution.row_count,
        "execution_time_ms": execution.execution_time_ms,
        "chart_recommendation": execution.chart_recommendation_json,
        "error_message": execution.error_message,
        "created_at": execution.created_at,
    }
    return QueryExecutionRead.model_validate(payload)


def _session_detail_to_read(session: ChatSessionModel) -> ChatSessionDetail:
    messages = [_message_to_read(message) for message in session.messages]
    last_execution = _execution_to_read(session.executions[-1]) if session.executions else None
    return ChatSessionDetail.model_validate(
        {
            **_session_to_read(session).model_dump(mode="json"),
            "messages": messages,
            "last_execution": last_execution,
        }
    )


def _get_session_or_404(db: Session, session_id: str) -> ChatSessionModel:
    session = chat_service.get_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return session


def _get_database_or_404(db: Session, database_id: str) -> None:
    databases = chat_service.workspace_service.list_databases(db)
    if not any(database.id == database_id for database in databases):
        raise HTTPException(status_code=404, detail="Database not found.")


@router.get("/chat/databases", response_model=list[DatabaseDescriptor])
def list_databases(db: Session = Depends(get_db)) -> list[DatabaseDescriptor]:
    return chat_service.list_databases(db)


@router.get("/chat/databases/{database_id}/sessions", response_model=list[ChatSessionRead])
def list_sessions(database_id: str, db: Session = Depends(get_db)) -> list[ChatSessionRead]:
    _get_database_or_404(db, database_id)
    sessions = chat_service.list_sessions(db, database_id)
    return [_session_to_read(session) for session in sessions]


@router.post("/chat/databases/{database_id}/sessions", response_model=ChatSessionRead, status_code=201)
def create_session(
    database_id: str,
    payload: ChatSessionCreate | None = None,
    db: Session = Depends(get_db),
) -> ChatSessionRead:
    _get_database_or_404(db, database_id)
    session = chat_service.create_session(db, database_id, payload)
    return _session_to_read(session)


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionDetail)
def get_session(session_id: str, db: Session = Depends(get_db)) -> ChatSessionDetail:
    session = _get_session_or_404(db, session_id)
    return _session_detail_to_read(session)


@router.patch("/chat/sessions/{session_id}", response_model=ChatSessionRead)
def update_session(
    session_id: str,
    payload: ChatSessionUpdate,
    db: Session = Depends(get_db),
) -> ChatSessionRead:
    session = _get_session_or_404(db, session_id)
    if payload.title is not None:
        session = chat_service.rename_session(db, session_id, payload.title) or session
    if payload.archived is not None:
        session = chat_service.archive_session(db, session_id, payload.archived) or session
    return _session_to_read(session)


@router.delete("/chat/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, db: Session = Depends(get_db)) -> Response:
    if not chat_service.delete_session(db, session_id):
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return Response(status_code=204)


@router.post("/chat/sessions/{session_id}/messages", response_model=SendMessageResponse, status_code=201)
async def send_message(
    session_id: str,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
) -> SendMessageResponse:
    _get_session_or_404(db, session_id)
    if not _try_mark_session_busy(session_id):
        raise HTTPException(status_code=409, detail="Chat session is busy.")

    try:
        result = chat_adapter.generate_response(db, session_id, payload.text)
        return SendMessageResponse(
            session=_session_to_read(result.session),
            user_message=_message_to_read(result.user_message),
            assistant_message=_message_to_read(result.assistant_message),
            sql_draft=result.sql_draft,
            sql_draft_version=result.sql_draft_version,
        )
    finally:
        _release_session_busy(session_id)


@router.patch("/chat/sessions/{session_id}/sql-draft", response_model=ChatSessionRead)
def update_sql_draft(
    session_id: str,
    payload: SqlDraftUpdate,
    db: Session = Depends(get_db),
) -> ChatSessionRead:
    _get_session_or_404(db, session_id)
    try:
        chat_service.update_sql_draft(db, session_id, payload.sql, payload.expected_version)
    except SqlDraftConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    session = _get_session_or_404(db, session_id)
    return _session_to_read(session)


@router.post("/chat/sessions/{session_id}/execute", response_model=ExecuteResponse, status_code=201)
def execute_sql(
    session_id: str,
    payload: ExecuteRequest,
    db: Session = Depends(get_db),
) -> ExecuteResponse:
    _get_session_or_404(db, session_id)
    try:
        execution = chat_execution_service.execute(db, session_id, payload.sql)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = _get_session_or_404(db, session_id)
    return ExecuteResponse(session=_session_to_read(session), execution=_execution_to_read(execution))
