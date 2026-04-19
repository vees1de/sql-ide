from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _engine_kwargs(url: str) -> dict:
    if url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    }


service_engine = create_engine(settings.service_database_url, future=True, **_engine_kwargs(settings.service_database_url))
analytics_engine = create_engine(
    settings.analytics_database_url,
    future=True,
    **_engine_kwargs(settings.analytics_database_url),
)

ServiceSessionLocal = sessionmaker(bind=service_engine, autocommit=False, autoflush=False, class_=Session)


def get_service_session() -> Session:
    db = ServiceSessionLocal()
    try:
        yield db
    finally:
        db.close()
