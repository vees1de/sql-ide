from __future__ import annotations

from fastapi import APIRouter

from app.schemas.metadata import SchemaMetadataResponse
from app.services.metadata_service import MetadataService
from app.services.query_templates import get_query_templates


router = APIRouter()
metadata_service = MetadataService()


@router.get("/metadata/schema", response_model=SchemaMetadataResponse)
def get_schema() -> SchemaMetadataResponse:
    return metadata_service.get_schema()


@router.get("/query-templates")
def list_query_templates() -> list[dict]:
    return get_query_templates()
