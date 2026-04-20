from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.knowledge import (
    ERDGraphResponse,
    KnowledgeColumnUpdate,
    KnowledgeRelationshipUpdate,
    KnowledgeScanRunRead,
    KnowledgeSummaryResponse,
    KnowledgeTableRead,
    KnowledgeTableUpdate,
)
from app.services.knowledge_service import KnowledgeService


router = APIRouter()
knowledge_service = KnowledgeService()


@router.post("/db-connections/{database_id}/scan/full", response_model=KnowledgeScanRunRead)
def scan_database_full(database_id: str, db: Session = Depends(get_db)) -> KnowledgeScanRunRead:
    try:
        return knowledge_service.scan_database(db, database_id, scan_type="full")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to scan database: {exc}") from exc


@router.post("/db-connections/{database_id}/scan/incremental", response_model=KnowledgeScanRunRead)
def scan_database_incremental(database_id: str, db: Session = Depends(get_db)) -> KnowledgeScanRunRead:
    try:
        return knowledge_service.scan_database(db, database_id, scan_type="incremental")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Failed to scan database: {exc}") from exc


@router.get("/db-connections/{database_id}/scan-runs", response_model=list[KnowledgeScanRunRead])
def list_scan_runs(database_id: str, db: Session = Depends(get_db)) -> list[KnowledgeScanRunRead]:
    return knowledge_service.list_scan_runs(db, database_id)


@router.get("/scan-runs/{scan_run_id}", response_model=KnowledgeScanRunRead)
def get_scan_run(scan_run_id: str, db: Session = Depends(get_db)) -> KnowledgeScanRunRead:
    scan_run = knowledge_service.get_scan_run(db, scan_run_id)
    if scan_run is None:
        raise HTTPException(status_code=404, detail="Scan run not found.")
    return scan_run


@router.get("/databases/{database_id}/knowledge", response_model=KnowledgeSummaryResponse)
def get_database_knowledge(database_id: str, db: Session = Depends(get_db)) -> KnowledgeSummaryResponse:
    try:
        return knowledge_service.get_summary(db, database_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tables/{table_id}", response_model=KnowledgeTableRead)
def get_knowledge_table(table_id: str, db: Session = Depends(get_db)) -> KnowledgeTableRead:
    table = knowledge_service.get_table(db, table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Knowledge table not found.")
    return knowledge_service.serialize_table(table)


@router.patch("/tables/{table_id}", response_model=KnowledgeTableRead)
def update_knowledge_table(
    table_id: str,
    payload: KnowledgeTableUpdate,
    db: Session = Depends(get_db),
) -> KnowledgeTableRead:
    table = knowledge_service.update_table(db, table_id, payload)
    if table is None:
        raise HTTPException(status_code=404, detail="Knowledge table not found.")
    reloaded = knowledge_service.get_table(db, table.id)
    if reloaded is None:
        raise HTTPException(status_code=404, detail="Knowledge table not found.")
    return knowledge_service.serialize_table(reloaded)


@router.patch("/columns/{column_id}", response_model=KnowledgeTableRead)
def update_knowledge_column(
    column_id: str,
    payload: KnowledgeColumnUpdate,
    db: Session = Depends(get_db),
) -> KnowledgeTableRead:
    column = knowledge_service.update_column(db, column_id, payload)
    if column is None:
        raise HTTPException(status_code=404, detail="Knowledge column not found.")
    table = knowledge_service.get_table(db, column.table_id)
    if table is None:
        raise HTTPException(status_code=404, detail="Knowledge table not found.")
    return knowledge_service.serialize_table(table)


@router.patch("/relationships/{relationship_id}", response_model=KnowledgeTableRead)
def update_knowledge_relationship(
    relationship_id: str,
    payload: KnowledgeRelationshipUpdate,
    db: Session = Depends(get_db),
) -> KnowledgeTableRead:
    relationship = knowledge_service.update_relationship(db, relationship_id, payload)
    if relationship is None:
        raise HTTPException(status_code=404, detail="Knowledge relationship not found.")
    source_table = knowledge_service.get_table_by_key(
        db,
        relationship.database_id,
        relationship.from_schema_name,
        relationship.from_table_name,
    )
    if source_table is None:
        raise HTTPException(status_code=404, detail="Knowledge table not found.")
    return knowledge_service.serialize_table(source_table)


@router.get("/databases/{database_id}/erd", response_model=ERDGraphResponse)
def get_database_erd(database_id: str, db: Session = Depends(get_db)) -> ERDGraphResponse:
    return knowledge_service.build_erd(db, database_id)
