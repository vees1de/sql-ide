from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.workspace import (
    DatabaseConnectionCreate,
    DatabaseConnectionUpdate,
    DatabaseDescriptor,
    SchemaPreviewResponse,
    WorkspaceCreate,
    WorkspaceRead,
)
from app.services.workspace_service import WorkspaceService


router = APIRouter()
workspace_service = WorkspaceService()


@router.get("/workspaces", response_model=list[WorkspaceRead])
def list_workspaces(db: Session = Depends(get_db)) -> list[WorkspaceRead]:
    return workspace_service.list_workspaces(db)


@router.post("/workspaces", response_model=WorkspaceRead, status_code=201)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db)) -> WorkspaceRead:
    return workspace_service.create_workspace(db, payload)


@router.get("/databases", response_model=list[DatabaseDescriptor])
def list_databases(db: Session = Depends(get_db)) -> list[DatabaseDescriptor]:
    return workspace_service.list_databases(db)


@router.post("/databases/preview-schema", response_model=SchemaPreviewResponse)
def preview_database_schema(
    payload: DatabaseConnectionCreate, db: Session = Depends(get_db)
) -> SchemaPreviewResponse:
    del db  # unused; keeps signature consistent with other routes
    try:
        return workspace_service.preview_schema(payload)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Cannot introspect database: {exc}") from exc


@router.post("/databases", response_model=DatabaseDescriptor, status_code=201)
def create_database(
    payload: DatabaseConnectionCreate, db: Session = Depends(get_db)
) -> DatabaseDescriptor:
    connection, imported = workspace_service.create_database(db, payload)
    allowed = connection.allowed_tables
    allowed_list = allowed if isinstance(allowed, list) else None
    return DatabaseDescriptor(
        id=connection.id,
        name=connection.name,
        dialect=connection.dialect,
        description=connection.description or "",
        read_only=(connection.read_only or "true").lower() == "true",
        is_demo=False,
        host=connection.host,
        port=connection.port,
        database=connection.database,
        username=connection.username,
        table_count=connection.table_count or 0,
        status=connection.status or "connected",
        allowed_tables=allowed_list,
        dictionary_entries_imported=imported if imported else None,
    )


@router.patch("/databases/{database_id}", response_model=DatabaseDescriptor)
def update_database(
    database_id: str, payload: DatabaseConnectionUpdate, db: Session = Depends(get_db)
) -> DatabaseDescriptor:
    connection = workspace_service.update_database(db, database_id, payload)
    if connection is None:
        raise HTTPException(status_code=404, detail="Database not found or cannot be updated.")
    allowed = connection.allowed_tables
    allowed_list = allowed if isinstance(allowed, list) else None
    return DatabaseDescriptor(
        id=connection.id,
        name=connection.name,
        dialect=connection.dialect,
        description=connection.description or "",
        read_only=(connection.read_only or "true").lower() == "true",
        is_demo=False,
        host=connection.host,
        port=connection.port,
        database=connection.database,
        username=connection.username,
        table_count=connection.table_count or 0,
        status=connection.status or "connected",
        allowed_tables=allowed_list,
    )


@router.delete("/databases/{database_id}", status_code=204)
def delete_database(database_id: str, db: Session = Depends(get_db)) -> Response:
    deleted = workspace_service.delete_database(db, database_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Database not found or is read-only.")
    return Response(status_code=204)
