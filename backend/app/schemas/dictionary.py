from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DictionaryEntryCreate(BaseModel):
    term: str = Field(min_length=1, max_length=255)
    synonyms: list[str] = Field(default_factory=list)
    mapped_expression: str = Field(min_length=1, max_length=255)
    description: str = ""


class DictionaryEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    term: str
    synonyms: list[str]
    mapped_expression: str
    description: str
    created_at: datetime
    updated_at: datetime
