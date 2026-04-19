from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.dictionary import DictionaryEntryCreate, DictionaryEntryRead
from app.services.dictionary_service import DictionaryService


router = APIRouter()
dictionary_service = DictionaryService()


@router.get("/semantic-dictionary", response_model=list[DictionaryEntryRead])
def list_dictionary_entries(db: Session = Depends(get_db)) -> list[DictionaryEntryRead]:
    return dictionary_service.list_entries(db)


@router.post("/semantic-dictionary", response_model=DictionaryEntryRead, status_code=201)
def create_dictionary_entry(payload: DictionaryEntryCreate, db: Session = Depends(get_db)) -> DictionaryEntryRead:
    return dictionary_service.create_entry(db, payload)
