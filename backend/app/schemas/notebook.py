from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.query import CellRead, QueryMode, QueryRunRead


class NotebookCreate(BaseModel):
    workspace_id: str
    title: str = Field(min_length=1, max_length=255)
    database_id: str = Field(min_length=1, max_length=255)


class NotebookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None


class NotebookCellCreate(BaseModel):
    type: Literal["prompt", "sql"]
    content: dict[str, Any] = Field(default_factory=dict)


class NotebookCellUpdate(BaseModel):
    content: dict[str, Any] = Field(default_factory=dict)


class NotebookCellReorder(BaseModel):
    ordered_cell_ids: list[str] = Field(default_factory=list)


class NotebookCellRunRequest(BaseModel):
    query_mode: QueryMode | None = None
    llm_model_alias: str | None = None


class NotebookRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    workspace_id: str
    title: str
    database_id: str
    status: str
    created_at: datetime
    updated_at: datetime


class NotebookDetail(NotebookRead):
    cells: list[CellRead] = Field(default_factory=list)
    query_runs: list[QueryRunRead] = Field(default_factory=list)
