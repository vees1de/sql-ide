from __future__ import annotations

import threading

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.models import ChatMessageModel, ChatSessionModel, QueryExecutionModel
from app.schemas.chat import (
    ChartSuggestionRequest,
    ExplainSqlRequest,
    ChatMessageCreate,
    ChatMessageRead,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionRead,
    ChatSessionUpdate,
    ClarificationAnswerRequest,
    ExecuteRequest,
    ExecuteResponse,
    PrepareSqlResponse,
    QueryExecutionRead,
    SqlExplanationResponse,
    RunPreparedSqlRequest,
    SendMessageResponse,
    SqlDraftUpdate,
)
from app.schemas.workspace import DatabaseDescriptor
from app.services.chat_execution_service import ChatExecutionService
from app.services.chat_service import ChatService, SqlDraftConflictError
from app.services.chat_sql_adapter import ChatSqlAdapter
from app.services.database_resolution import resolve_dialect


router = APIRouter()
chat_service = ChatService()
chat_adapter = ChatSqlAdapter()
chat_execution_service = ChatExecutionService()
llm_service = chat_execution_service.llm_service

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
        "dataset": {
            "dataset_id": f"query_execution:{execution.id}",
            "query_execution_id": execution.id,
            "row_count": execution.row_count,
            "columns": execution.columns_json or [],
        },
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
        result = chat_adapter.generate_response(
            db,
            session_id,
            payload.text,
            query_mode=payload.query_mode,
            llm_model_alias=payload.llm_model_alias,
        )
        return SendMessageResponse(
            session=_session_to_read(result.session),
            user_message=_message_to_read(result.user_message),
            assistant_message=_message_to_read(result.assistant_message),
            sql_draft=result.sql_draft,
            sql_draft_version=result.sql_draft_version,
        )
    finally:
        _release_session_busy(session_id)


@router.post(
    "/chat/sessions/{session_id}/clarifications/{clarification_id}/answer",
    response_model=SendMessageResponse,
    status_code=201,
)
async def answer_clarification(
    session_id: str,
    clarification_id: str,
    payload: ClarificationAnswerRequest,
    db: Session = Depends(get_db),
) -> SendMessageResponse:
    _get_session_or_404(db, session_id)
    if not _try_mark_session_busy(session_id):
        raise HTTPException(status_code=409, detail="Chat session is busy.")

    try:
        result = chat_adapter.answer_clarification(
            db,
            session_id,
            clarification_id,
            payload,
        )
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


@router.post("/chat/sessions/{session_id}/actions/run-sql", response_model=ExecuteResponse, status_code=201)
def run_prepared_sql(
    session_id: str,
    payload: RunPreparedSqlRequest | None = None,
    db: Session = Depends(get_db),
) -> ExecuteResponse:
    _get_session_or_404(db, session_id)
    try:
        execution = chat_execution_service.execute_prepared(db, session_id, payload.sql if payload else None)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session = _get_session_or_404(db, session_id)
    return ExecuteResponse(session=_session_to_read(session), execution=_execution_to_read(execution))


@router.post("/chat/sessions/{session_id}/actions/explain-sql", response_model=SqlExplanationResponse)
def explain_sql(
    session_id: str,
    payload: ExplainSqlRequest | None = None,
    db: Session = Depends(get_db),
) -> SqlExplanationResponse:
    session = _get_session_or_404(db, session_id)
    sql_text = (payload.sql if payload and payload.sql is not None else session.current_sql_draft or "").strip()
    if not sql_text:
        raise HTTPException(status_code=400, detail="No SQL draft found for this session.")

    dialect = resolve_dialect(db, session.database_connection_id)
    explanation = llm_service.explain_sql(sql=sql_text, dialect=dialect)
    if explanation is None:
        raise HTTPException(status_code=500, detail="Failed to explain SQL.")
    return explanation


@router.post("/chat/sessions/{session_id}/actions/create-sql", response_model=PrepareSqlResponse, status_code=201)
def create_sql(
    session_id: str,
    db: Session = Depends(get_db),
) -> PrepareSqlResponse:
    _get_session_or_404(db, session_id)
    try:
        result = chat_adapter.prepare_sql(db, session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return PrepareSqlResponse(
        session=_session_to_read(result.session),
        assistant_message=_message_to_read(result.assistant_message),
        sql_draft=result.sql_draft,
        sql_draft_version=result.sql_draft_version,
    )


@router.post(
    "/chat/sessions/{session_id}/executions/{execution_id}/chart-suggestion",
    response_model=QueryExecutionRead,
    status_code=201,
)
def suggest_chart(
    session_id: str,
    execution_id: str,
    payload: ChartSuggestionRequest | None = None,
    db: Session = Depends(get_db),
) -> QueryExecutionRead:
    _get_session_or_404(db, session_id)
    try:
        execution = chat_execution_service.suggest_chart(
            db,
            session_id,
            execution_id,
            (payload.goal if payload else "best_chart"),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _execution_to_read(execution)
