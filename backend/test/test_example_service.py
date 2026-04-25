from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.models import DatabaseConnectionModel
from app.services.example_service import ExampleService


def _build_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    db.add(DatabaseConnectionModel(id="db-1", name="Demo DB", dialect="sqlite", read_only="true"))
    db.commit()
    return db


def test_save_example_deduplicates_same_prompt_and_sql() -> None:
    db = _build_db()
    service = ExampleService()

    first = service.save_example(db, "db-1", "prompt", "SELECT 1", source="auto", quality_score=1.0)
    second = service.save_example(db, "db-1", "prompt", "SELECT 1", source="manual", quality_score=1.4)

    assert first.id == second.id
    assert second.source == "manual"
    assert second.quality_score == 1.4
    assert len(service.list_examples(db, "db-1", active_only=False)) == 1
