from __future__ import annotations

import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.services.bootstrap import bootstrap_application
from app.services.dashboard_service import DashboardService


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap_application()
    stop_event = threading.Event()
    dashboard_service = DashboardService()

    def _run_scheduler() -> None:
        while not stop_event.wait(60):
            try:
                dashboard_service.dispatch_due_schedules()
            except Exception:  # noqa: BLE001
                continue

    scheduler_thread = threading.Thread(target=_run_scheduler, daemon=True)
    scheduler_thread.start()
    yield
    stop_event.set()
    scheduler_thread.join(timeout=2)


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allow_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/")
def root() -> dict:
    return {
        "name": settings.app_name,
        "docs": "/docs",
        "apiPrefix": settings.api_prefix,
    }
