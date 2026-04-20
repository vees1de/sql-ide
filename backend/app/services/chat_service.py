from __future__ import annotations

from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.models import ChatMessageModel, ChatSessionModel
from app.schemas.chat import ChatMessageCreate, ChatSessionCreate, ChatSessionUpdate
from app.schemas.workspace import DatabaseDescriptor
from app.services.database_resolution import resolve_dialect
from app.services.workspace_service import WorkspaceService


class SqlDraftConflictError(ValueError):
    pass


class ChatService:
    def __init__(self) -> None:
        self.workspace_service = WorkspaceService()

    def list_databases(self, db: Session) -> list[DatabaseDescriptor]:
        return self.workspace_service.list_databases(db)

    def list_sessions(self, db: Session, database_connection_id: str) -> list[ChatSessionModel]:
        return (
            db.query(ChatSessionModel)
            .filter(
                ChatSessionModel.database_connection_id == database_connection_id,
                ChatSessionModel.archived.is_(False),
            )
            .order_by(ChatSessionModel.updated_at.desc(), ChatSessionModel.created_at.desc())
            .all()
        )

    def create_session(
        self,
        db: Session,
        database_connection_id: str,
        payload: ChatSessionCreate | None = None,
    ) -> ChatSessionModel:
        resolve_dialect(db, database_connection_id)
        title = (payload.title if payload and payload.title else "Новый чат").strip()
        if not title:
            title = "Новый чат"

        session = ChatSessionModel(
            database_connection_id=database_connection_id,
            title=title,
            current_sql_draft=None,
            sql_draft_version=0,
            last_executed_sql=None,
            last_intent_json=None,
            archived=False,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session

    def get_session(self, db: Session, session_id: str) -> ChatSessionModel | None:
        return (
            db.query(ChatSessionModel)
            .options(
                selectinload(ChatSessionModel.messages),
                selectinload(ChatSessionModel.executions),
            )
            .filter(ChatSessionModel.id == session_id)
            .first()
        )

    def rename_session(self, db: Session, session_id: str, title: str) -> ChatSessionModel | None:
        session = self.get_session(db, session_id)
        if session is None:
            return None
        session.title = title.strip() or session.title
        db.commit()
        db.refresh(session)
        return session

    def archive_session(self, db: Session, session_id: str, archived: bool = True) -> ChatSessionModel | None:
        session = self.get_session(db, session_id)
        if session is None:
            return None
        session.archived = archived
        db.commit()
        db.refresh(session)
        return session

    def delete_session(self, db: Session, session_id: str) -> bool:
        session = self.get_session(db, session_id)
        if session is None:
            return False
        db.delete(session)
        db.commit()
        return True

    def append_message(
        self,
        db: Session,
        session: ChatSessionModel,
        role: str,
        text: str,
        structured_payload: Any | None = None,
        *,
        commit: bool = True,
    ) -> ChatMessageModel:
        payload = jsonable_encoder(structured_payload) if structured_payload is not None else None
        message = ChatMessageModel(
            session_id=session.id,
            role=role,
            text=text,
            structured_payload=payload,
        )
        db.add(message)
        db.flush()
        if commit:
            db.commit()
            db.refresh(message)
        return message

    def update_sql_draft(
        self,
        db: Session,
        session_id: str,
        sql: str,
        expected_version: int,
        *,
        commit: bool = True,
    ) -> tuple[bool, int]:
        session = self.get_session(db, session_id)
        if session is None:
            raise ValueError("Chat session not found.")
        if expected_version != session.sql_draft_version:
            raise SqlDraftConflictError(
                f"SQL draft version mismatch. Expected {expected_version}, found {session.sql_draft_version}."
            )

        session.current_sql_draft = sql
        session.sql_draft_version = (session.sql_draft_version or 0) + 1
        db.flush()
        if commit:
            db.commit()
            db.refresh(session)
        return True, session.sql_draft_version

    def update_session_fields(
        self,
        db: Session,
        session_id: str,
        *,
        title: str | None = None,
        archived: bool | None = None,
        current_sql_draft: str | None = None,
        last_intent_json: dict[str, Any] | None = None,
        last_executed_sql: str | None = None,
        increment_sql_version: bool = False,
        commit: bool = True,
    ) -> ChatSessionModel | None:
        session = self.get_session(db, session_id)
        if session is None:
            return None
        if title is not None:
            session.title = title.strip() or session.title
        if archived is not None:
            session.archived = archived
        if current_sql_draft is not None:
            session.current_sql_draft = current_sql_draft
            if increment_sql_version:
                session.sql_draft_version = (session.sql_draft_version or 0) + 1
        if last_intent_json is not None:
            session.last_intent_json = last_intent_json
        if last_executed_sql is not None:
            session.last_executed_sql = last_executed_sql
        db.flush()
        if commit:
            db.commit()
            db.refresh(session)
        return session

    def title_from_prompt(self, prompt: str) -> str:
        cleaned = " ".join(prompt.strip().split())
        if not cleaned:
            return "Новый чат"
        return cleaned[:64].rstrip(" ,.;:") or "Новый чат"

    def maybe_auto_title(self, session: ChatSessionModel, prompt: str) -> str | None:
        if session.title and session.title != "Новый чат":
            return None
        return self.title_from_prompt(prompt)

