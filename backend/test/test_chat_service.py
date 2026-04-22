from __future__ import annotations

from app.db.models import ChatMessageModel, ChatSessionModel
from app.services.chat_service import ChatService


class _FakeQuery:
    def __init__(self, sessions: list[ChatSessionModel]) -> None:
        self.sessions = sessions

    def options(self, *_args, **_kwargs) -> _FakeQuery:
        return self

    def filter(self, *_args, **_kwargs) -> _FakeQuery:
        return self

    def order_by(self, *_args, **_kwargs) -> _FakeQuery:
        return self

    def all(self) -> list[ChatSessionModel]:
        return list(self.sessions)


class _FakeDB:
    def __init__(self, sessions: list[ChatSessionModel] | None = None) -> None:
        self.sessions = sessions or []
        self.added: list[object] = []
        self.commits = 0
        self.refreshed: list[object] = []

    def query(self, model: object) -> _FakeQuery:
        assert model is ChatSessionModel
        return _FakeQuery(self.sessions)

    def add(self, obj: object) -> None:
        self.added.append(obj)
        if isinstance(obj, ChatSessionModel):
            self.sessions.append(obj)

    def commit(self) -> None:
        self.commits += 1

    def refresh(self, obj: object) -> None:
        self.refreshed.append(obj)


def _build_session(**overrides: object) -> ChatSessionModel:
    session = ChatSessionModel(
        id="sess-1",
        database_connection_id="db-1",
        title="Новый чат",
        current_sql_draft=None,
        sql_draft_version=0,
        last_executed_sql=None,
        last_intent_json=None,
        archived=False,
    )
    session.messages = []
    session.executions = []
    for key, value in overrides.items():
        setattr(session, key, value)
    return session


def test_create_session_reuses_existing_empty_chat(monkeypatch) -> None:
    db = _FakeDB([_build_session()])
    service = ChatService()

    monkeypatch.setattr("app.services.chat_service.resolve_dialect", lambda *_args, **_kwargs: "postgres")

    session = service.create_session(db, "db-1")

    assert session is db.sessions[0]
    assert db.added == []
    assert db.commits == 0


def test_create_session_creates_new_chat_if_existing_one_has_messages(monkeypatch) -> None:
    existing = _build_session(messages=[ChatMessageModel(role="user", text="hello")])
    db = _FakeDB([existing])
    service = ChatService()

    monkeypatch.setattr("app.services.chat_service.resolve_dialect", lambda *_args, **_kwargs: "postgres")

    session = service.create_session(db, "db-1")

    assert session is not existing
    assert len(db.added) == 1
    assert isinstance(db.added[0], ChatSessionModel)
    assert db.commits == 1
