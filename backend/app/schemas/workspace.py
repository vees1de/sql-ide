from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DatabaseDescriptor(BaseModel):
    id: str
    name: str
    dialect: str
    description: str
    read_only: bool = True
    is_demo: bool = False
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    table_count: int = 0
    status: str = "connected"
    allowed_tables: list[str] | None = None
    dictionary_entries_imported: int | None = None


class DatabaseConnectionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    dialect: str = Field(default="postgresql", max_length=64)
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    database: str | None = None
    username: str | None = None
    password: str | None = None
    description: str = ""
    read_only: bool = True
    table_count: int = 0
    import_schema_to_dictionary: bool = False
    allowed_tables: list[str] | None = None


class DatabaseConnectionUpdate(BaseModel):
    allowed_tables: list[str] | None = None


class SchemaPreviewTable(BaseModel):
    name: str
    columns: list[str]


class SchemaPreviewResponse(BaseModel):
    tables: list[SchemaPreviewTable]
    table_names: list[str]


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    databases: list[str] = Field(default_factory=list)


class WorkspaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    databases: list[str]
    created_at: datetime
    updated_at: datetime
