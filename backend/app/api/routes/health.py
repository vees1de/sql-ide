from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import analytics_engine, service_engine


router = APIRouter()


@router.get("/health")
def healthcheck() -> dict:
    service_ok = False
    analytics_ok = False

    try:
        with service_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        service_ok = True
    except Exception:  # noqa: BLE001
        service_ok = False

    try:
        with analytics_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        analytics_ok = True
    except Exception:  # noqa: BLE001
        analytics_ok = False

    return {
        "status": "ok" if service_ok and analytics_ok else "degraded",
        "app": settings.app_name,
        "environment": settings.environment,
        "embeddedAnalytics": settings.embedded_analytics_enabled,
        "llm": {
            "configured": bool(settings.llm_api_base_url and settings.llm_api_key and settings.llm_model),
            "baseUrl": settings.llm_api_base_url,
            "model": settings.llm_model,
        },
        "serviceDatabase": {
            "ok": service_ok,
            "dialect": service_engine.dialect.name,
        },
        "analyticsDatabase": {
            "ok": analytics_ok,
            "dialect": analytics_engine.dialect.name,
        },
    }
