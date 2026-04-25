from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChatMessageModel, ChatSessionModel, DatabaseConnectionModel, DatasetModel, QueryExampleModel, QueryExecutionModel
from app.schemas.query import ChartEncoding, ChartSpec
from app.services.chat_execution_service import ChatExecutionService


def _build_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE numbers (
              id INTEGER PRIMARY KEY,
              value INTEGER NOT NULL
            )
            """
        )
        connection.exec_driver_sql(
            """
            INSERT INTO numbers (id, value) VALUES (1, 10), (2, 20)
            """
        )

    db.add(DatabaseConnectionModel(id="db-1", name="Demo DB", dialect="sqlite", read_only="true"))
    db.add(
        ChatSessionModel(
            id="session-1",
            database_connection_id="db-1",
            title="Revenue chat",
            current_sql_draft=None,
            sql_draft_version=0,
            last_executed_sql=None,
            last_intent_json=None,
            archived=False,
        )
    )
    db.commit()
    return db, engine


def _add_chat_messages(
    db,
    *,
    session_id: str = "session-1",
    prompt: str = "Покажи id и value",
    sql: str = "SELECT id, value FROM numbers ORDER BY id",
    rag_example_candidate: bool = True,
) -> None:
    db.add(
        ChatMessageModel(
            session_id=session_id,
            role="user",
            text=prompt,
            structured_payload=None,
        )
    )
    db.add(
        ChatMessageModel(
            session_id=session_id,
            role="assistant",
            text="SQL готов.",
            structured_payload={
                "state": "SQL_READY",
                "sql": sql,
                "rag_example_candidate": rag_example_candidate,
            },
        )
    )
    db.commit()


def test_execute_creates_persisted_dataset(monkeypatch) -> None:
    db, engine = _build_session()
    _add_chat_messages(db)
    service = ChatExecutionService()
    sql = "SELECT id, value FROM numbers ORDER BY id"

    monkeypatch.setattr("app.services.chat_execution_service.resolve_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setattr("app.services.chat_execution_service.resolve_dialect", lambda *_args, **_kwargs: "sqlite")
    monkeypatch.setattr("app.services.chat_execution_service.resolve_allowed_tables", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_dry_run_query", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_read_dataframe", lambda *_args, **_kwargs: pd.read_sql_query(sql, engine))
    monkeypatch.setattr(service.schema_provider, "get_schema_for_llm", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service.semantic_catalog_service, "load_catalog", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service.validation_agent,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(valid=True, sql=sql, errors=[]),
    )
    monkeypatch.setattr(service, "_build_repair_context", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(service, "_attempt_repair", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service.chart_service,
        "decide",
        lambda *_args, **_kwargs: SimpleNamespace(
            chart_type="bar",
            encoding=SimpleNamespace(
                x_field="id",
                y_field="value",
                series_field=None,
                facet_field=None,
                sort=None,
                normalize=None,
                value_format=None,
                series_limit=None,
                category_limit=None,
                top_n_strategy=None,
            ),
            variant=None,
            explanation="ok",
            reason="ok",
            rule_id="rule",
            confidence=1.0,
            semantic_intent=None,
            analysis_mode=None,
            visual_goal=None,
            time_role=None,
            comparison_goal=None,
            preferred_mark=None,
            alternatives=[],
            candidates=[],
            constraints_applied=[],
            visual_load=None,
            query_interpretation=None,
            decision_summary=None,
            reason_codes=[],
        ),
    )
    monkeypatch.setattr(
        service.chart_spec_service,
        "from_decision",
        lambda *_args, **_kwargs: ChartSpec(
            chart_type="bar",
            title="Автоматическая визуализация",
            encoding=ChartEncoding(x_field="id", y_field="value"),
            reason="ok",
        ),
    )

    execution = service.execute(db, "session-1", sql)

    assert execution.dataset_id is not None
    assert execution.dataset is not None
    assert execution.dataset.name == "Revenue chat"
    assert execution.dataset.sql == sql
    assert execution.dataset.row_count == 2
    assert execution.dataset.preview_rows == [{"id": 1, "value": 10}, {"id": 2, "value": 20}]

    persisted_execution = db.query(QueryExecutionModel).filter(QueryExecutionModel.id == execution.id).one()
    persisted_dataset = db.query(DatasetModel).filter(DatasetModel.id == execution.dataset_id).one()

    assert persisted_execution.dataset_id == persisted_dataset.id
    assert persisted_dataset.source_query_execution_id == execution.id


def test_execute_saves_direct_sql_as_rag_example(monkeypatch) -> None:
    db, engine = _build_session()
    sql = "SELECT id, value FROM numbers ORDER BY id"
    _add_chat_messages(db, sql=sql, rag_example_candidate=True)
    service = ChatExecutionService()

    monkeypatch.setattr("app.services.chat_execution_service.resolve_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setattr("app.services.chat_execution_service.resolve_dialect", lambda *_args, **_kwargs: "sqlite")
    monkeypatch.setattr("app.services.chat_execution_service.resolve_allowed_tables", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_dry_run_query", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_read_dataframe", lambda *_args, **_kwargs: pd.read_sql_query(sql, engine))
    monkeypatch.setattr(service.schema_provider, "get_schema_for_llm", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service.semantic_catalog_service, "load_catalog", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service.validation_agent,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(valid=True, sql=sql, errors=[]),
    )
    monkeypatch.setattr(service, "_build_repair_context", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(service, "_attempt_repair", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service.chart_service,
        "decide",
        lambda *_args, **_kwargs: SimpleNamespace(
            chart_type="bar",
            encoding=SimpleNamespace(
                x_field="id",
                y_field="value",
                series_field=None,
                facet_field=None,
                sort=None,
                normalize=None,
                value_format=None,
                series_limit=None,
                category_limit=None,
                top_n_strategy=None,
            ),
            variant=None,
            explanation="ok",
            reason="ok",
            rule_id="rule",
            confidence=1.0,
            semantic_intent=None,
            analysis_mode=None,
            visual_goal=None,
            time_role=None,
            comparison_goal=None,
            preferred_mark=None,
            alternatives=[],
            candidates=[],
            constraints_applied=[],
            visual_load=None,
            query_interpretation=None,
            decision_summary=None,
            reason_codes=[],
        ),
    )
    monkeypatch.setattr(
        service.chart_spec_service,
        "from_decision",
        lambda *_args, **_kwargs: ChartSpec(
            chart_type="bar",
            title="Автоматическая визуализация",
            encoding=ChartEncoding(x_field="id", y_field="value"),
            reason="ok",
        ),
    )

    service.execute(db, "session-1", sql)

    examples = db.query(QueryExampleModel).all()
    assert len(examples) == 1
    assert examples[0].prompt == "Покажи id и value"
    assert examples[0].sql == sql
    assert examples[0].source == "auto"


def test_execute_does_not_save_non_immediate_sql_as_rag_example(monkeypatch) -> None:
    db, engine = _build_session()
    sql = "SELECT id, value FROM numbers ORDER BY id"
    repaired_sql = "SELECT value, id FROM numbers ORDER BY id"
    _add_chat_messages(db, sql=sql, rag_example_candidate=True)
    service = ChatExecutionService()

    monkeypatch.setattr("app.services.chat_execution_service.resolve_engine", lambda *_args, **_kwargs: engine)
    monkeypatch.setattr("app.services.chat_execution_service.resolve_dialect", lambda *_args, **_kwargs: "sqlite")
    monkeypatch.setattr("app.services.chat_execution_service.resolve_allowed_tables", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_dry_run_query", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_read_dataframe", lambda *_args, **_kwargs: pd.read_sql_query(repaired_sql, engine))
    monkeypatch.setattr(service.schema_provider, "get_schema_for_llm", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service.semantic_catalog_service, "load_catalog", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service.validation_agent,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(valid=True, sql=repaired_sql, errors=[]),
    )
    monkeypatch.setattr(service, "_build_repair_context", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(service, "_attempt_repair", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service.chart_service,
        "decide",
        lambda *_args, **_kwargs: SimpleNamespace(
            chart_type="bar",
            encoding=SimpleNamespace(
                x_field="id",
                y_field="value",
                series_field=None,
                facet_field=None,
                sort=None,
                normalize=None,
                value_format=None,
                series_limit=None,
                category_limit=None,
                top_n_strategy=None,
            ),
            variant=None,
            explanation="ok",
            reason="ok",
            rule_id="rule",
            confidence=1.0,
            semantic_intent=None,
            analysis_mode=None,
            visual_goal=None,
            time_role=None,
            comparison_goal=None,
            preferred_mark=None,
            alternatives=[],
            candidates=[],
            constraints_applied=[],
            visual_load=None,
            query_interpretation=None,
            decision_summary=None,
            reason_codes=[],
        ),
    )
    monkeypatch.setattr(
        service.chart_spec_service,
        "from_decision",
        lambda *_args, **_kwargs: ChartSpec(
            chart_type="bar",
            title="Автоматическая визуализация",
            encoding=ChartEncoding(x_field="id", y_field="value"),
            reason="ok",
        ),
    )

    service.execute(db, "session-1", sql)

    assert db.query(QueryExampleModel).count() == 0
