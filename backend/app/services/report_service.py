from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import SavedReportModel
from app.schemas.report import ReportCreate


class ReportService:
    def list_reports(self, db: Session) -> list[SavedReportModel]:
        return db.query(SavedReportModel).order_by(SavedReportModel.created_at.desc()).all()

    def create_report(self, db: Session, payload: ReportCreate) -> SavedReportModel:
        report = SavedReportModel(
            notebook_id=payload.notebook_id,
            title=payload.title,
            schedule=payload.schedule,
        )
        db.add(report)
        db.commit()
        db.refresh(report)
        return report
