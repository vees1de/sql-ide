from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.widgets import WidgetRead


class DashboardWidgetLayout(BaseModel):
    x: int = 0
    y: int = 0
    w: int = 6
    h: int = 4


class DashboardWidgetCreate(BaseModel):
    widget_id: str
    layout: DashboardWidgetLayout = Field(default_factory=DashboardWidgetLayout)
    title_override: str | None = None
    display_options: dict[str, Any] | None = None


class DashboardWidgetUpdate(BaseModel):
    layout: DashboardWidgetLayout | None = None
    title_override: str | None = None
    display_options: dict[str, Any] | None = None


class DashboardWidgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dashboard_id: str
    widget_id: str
    title_override: str | None = None
    layout: dict[str, Any]
    display_options: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class DashboardWidgetDetail(DashboardWidgetRead):
    widget: WidgetRead


class DashboardCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    is_public: bool = False
    widgets: list[DashboardWidgetCreate] = Field(default_factory=list)


class DashboardUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    is_public: bool | None = None
    slug: str | None = None


class DashboardRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None = None
    slug: str | None = None
    layout_type: str
    is_public: bool
    owner_id: str
    created_at: datetime
    updated_at: datetime


class DashboardDetail(DashboardRead):
    widgets: list[DashboardWidgetDetail] = Field(default_factory=list)
