from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.report import ReportCreate, ReportRead
from app.services.report_service import ReportService


router = APIRouter()
report_service = ReportService()


@router.get("/reports", response_model=list[ReportRead])
def list_reports(db: Session = Depends(get_db)) -> list[ReportRead]:
    return report_service.list_reports(db)


@router.post("/reports", response_model=ReportRead, status_code=201)
def create_report(payload: ReportCreate, db: Session = Depends(get_db)) -> ReportRead:
    return report_service.create_report(db, payload)
