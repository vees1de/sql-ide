from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.core.config import (
    YANDEX_MODEL_ALIASES,
    detect_llm_model_alias,
    settings,
)
from app.schemas.metadata import SchemaMetadataResponse
from app.schemas.metadata import LLMModelAliasItem, LLMModelAliasesResponse
from app.schemas.semantic_catalog import (
    SemanticCatalog,
    SemanticCatalogActivationRequest,
    SemanticColumnPatch,
    SemanticTable,
    SemanticTablePatch,
)
from app.api.deps import get_db
from app.services.metadata_service import MetadataService
from app.services.semantic_catalog_service import SemanticCatalogService
from app.services.query_templates import get_query_templates


router = APIRouter()
metadata_service = MetadataService()
semantic_catalog_service = SemanticCatalogService()


@router.get("/metadata/schema", response_model=SchemaMetadataResponse)
def get_schema() -> SchemaMetadataResponse:
    return metadata_service.get_schema()


@router.get("/metadata/semantic-catalog", response_model=SemanticCatalog)
def get_semantic_catalog(
    database_id: str = settings.analytics_database_id,
    refresh: bool = False,
    db: Session = Depends(get_db),
) -> SemanticCatalog:
    return semantic_catalog_service.get_catalog(db, database_id, refresh=refresh)


@router.post("/metadata/semantic-catalog/activate", response_model=SemanticCatalog)
def activate_semantic_catalog(
    payload: SemanticCatalogActivationRequest,
    db: Session = Depends(get_db),
) -> SemanticCatalog:
    return semantic_catalog_service.activate_catalog(
        db,
        payload.database_id,
        refresh=payload.refresh,
        database_description=payload.database_description,
        table_descriptions=payload.table_descriptions,
        relationship_descriptions=payload.relationship_descriptions,
        column_descriptions=payload.column_descriptions,
    )


@router.delete("/metadata/semantic-catalog", status_code=204)
def delete_semantic_catalog(
    database_id: str,
    db: Session = Depends(get_db),
) -> Response:
    deleted = semantic_catalog_service.delete_active_catalog(db, database_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No active semantic catalog found.")
    return Response(status_code=204)


@router.patch("/metadata/semantic-catalog/table", response_model=SemanticTable)
def patch_semantic_table(
    database_id: str,
    table_name: str,
    payload: SemanticTablePatch,
    db: Session = Depends(get_db),
) -> SemanticTable:
    result = semantic_catalog_service.patch_catalog_table(db, database_id, table_name, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Table not found in active catalog.")
    return result


@router.patch("/metadata/semantic-catalog/column", response_model=SemanticTable)
def patch_semantic_column(
    database_id: str,
    table_name: str,
    column_name: str,
    payload: SemanticColumnPatch,
    db: Session = Depends(get_db),
) -> SemanticTable:
    result = semantic_catalog_service.patch_catalog_column(db, database_id, table_name, column_name, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Column not found in active catalog.")
    return result


@router.get("/query-templates")
def list_query_templates() -> list[dict]:
    return get_query_templates()


@router.get("/metadata/llm-models", response_model=LLMModelAliasesResponse)
def list_llm_models() -> LLMModelAliasesResponse:
    return LLMModelAliasesResponse(
        aliases=[
            LLMModelAliasItem(alias=alias, model=model)
            for alias, model in YANDEX_MODEL_ALIASES.items()
        ],
        default_alias=detect_llm_model_alias(None),
        current_alias=detect_llm_model_alias(settings.llm_model),
    )
