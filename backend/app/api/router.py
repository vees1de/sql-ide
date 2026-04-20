from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import analytics, chat, dashboards, dictionary, health, knowledge, metadata, notebooks, reports, widgets, workspaces


api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(workspaces.router, prefix="", tags=["workspaces"])
api_router.include_router(notebooks.router, prefix="", tags=["notebooks"])
api_router.include_router(chat.router, prefix="", tags=["chat"])
api_router.include_router(analytics.router, prefix="", tags=["analytics"])
api_router.include_router(reports.router, prefix="", tags=["reports"])
api_router.include_router(dictionary.router, prefix="", tags=["semantic-dictionary"])
api_router.include_router(metadata.router, prefix="", tags=["metadata"])
api_router.include_router(knowledge.router, prefix="", tags=["knowledge"])
api_router.include_router(widgets.router, prefix="", tags=["widgets"])
api_router.include_router(dashboards.router, prefix="", tags=["dashboards"])
