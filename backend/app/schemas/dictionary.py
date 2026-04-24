from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DictionaryEntryCreate(BaseModel):
    term: str = Field(min_length=1, max_length=255)
    synonyms: list[str] = Field(default_factory=list)
    mapped_expression: str = Field(min_length=1, max_length=255)
    description: str = ""
    object_type: str | None = Field(default=None, max_length=32)
    table_name: str | None = Field(default=None, max_length=255)
    column_name: str | None = Field(default=None, max_length=255)
    database_id: str | None = Field(default=None, max_length=32)
    source_database: str | None = Field(default=None, max_length=255)


class DictionaryEntryUpdate(BaseModel):
    term: str | None = Field(default=None, min_length=1, max_length=255)
    synonyms: list[str] | None = None
    mapped_expression: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    object_type: str | None = Field(default=None, max_length=32)
    table_name: str | None = Field(default=None, max_length=255)
    column_name: str | None = Field(default=None, max_length=255)
    database_id: str | None = Field(default=None, max_length=32)
    source_database: str | None = Field(default=None, max_length=255)


class DictionaryImportSchemaRequest(BaseModel):
    database_id: str | None = Field(default=None, max_length=32)
    database_label: str = Field(min_length=1, max_length=255)
    tables: list[dict[str, object]] = Field(default_factory=list)
    max_entries: int = Field(default=2000, ge=1, le=10000)


class DictionaryImportSchemaResponse(BaseModel):
    imported: int


class DictionaryEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    term: str
    synonyms: list[str]
    mapped_expression: str
    description: str
    object_type: str | None = None
    table_name: str | None = None
    column_name: str | None = None
    database_id: str | None = None
    source_database: str | None = None
    created_at: datetime = datetime.min
    updated_at: datetime = datetime.min
