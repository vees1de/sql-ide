from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.dictionary import (
    DictionaryEntryCreate,
    DictionaryEntryRead,
    DictionaryEntryUpdate,
    DictionaryImportSchemaRequest,
    DictionaryImportSchemaResponse,
)
from app.services.dictionary_service import DictionaryService


router = APIRouter()
dictionary_service = DictionaryService()


@router.get("/semantic-dictionary", response_model=list[DictionaryEntryRead])
def list_dictionary_entries(
    database_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[DictionaryEntryRead]:
    return dictionary_service.list_entries(db, database_id=database_id)


@router.post("/semantic-dictionary", response_model=DictionaryEntryRead, status_code=201)
def create_dictionary_entry(payload: DictionaryEntryCreate, db: Session = Depends(get_db)) -> DictionaryEntryRead:
    return dictionary_service.create_entry(db, payload)


@router.patch("/semantic-dictionary/{entry_id}", response_model=DictionaryEntryRead)
def update_dictionary_entry(
    entry_id: str,
    payload: DictionaryEntryUpdate,
    db: Session = Depends(get_db),
) -> DictionaryEntryRead:
    updated = dictionary_service.update_entry(db, entry_id, payload)
    if updated is None:
        raise HTTPException(status_code=404, detail="Dictionary entry not found.")
    return updated


@router.delete("/semantic-dictionary/{entry_id}", status_code=204)
def delete_dictionary_entry(entry_id: str, db: Session = Depends(get_db)) -> Response:
    deleted = dictionary_service.delete_entry(db, entry_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Dictionary entry not found.")
    return Response(status_code=204)


@router.post("/semantic-dictionary/import-schema", response_model=DictionaryImportSchemaResponse)
def import_dictionary_from_schema(
    payload: DictionaryImportSchemaRequest,
    db: Session = Depends(get_db),
) -> DictionaryImportSchemaResponse:
    imported = dictionary_service.import_schema_tables(
        db=db,
        tables=payload.tables,
        database_id=payload.database_id,
        database_label=payload.database_label,
        max_entries=payload.max_entries,
    )
    return DictionaryImportSchemaResponse(imported=imported)
