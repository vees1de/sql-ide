from __future__ import annotations

from typing import Generator

from sqlalchemy.orm import Session

from app.db.session import get_service_session


def get_db() -> Generator[Session, None, None]:
    yield from get_service_session()
