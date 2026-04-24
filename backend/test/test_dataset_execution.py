from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import ChatSessionModel, DatabaseConnectionModel, DatasetModel, QueryExecutionModel
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


def test_execute_creates_persisted_dataset(monkeypatch) -> None:
    db, engine = _build_session()
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
