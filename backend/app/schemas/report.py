from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ReportCreate(BaseModel):
    notebook_id: str
    title: str = Field(min_length=1, max_length=255)
    schedule: str | None = None


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    notebook_id: str
    title: str
    schedule: str | None = None
    created_at: datetime
