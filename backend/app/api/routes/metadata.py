from __future__ import annotations

from fastapi import APIRouter

from app.core.config import (
    YANDEX_MODEL_ALIASES,
    detect_llm_model_alias,
    settings,
)
from app.schemas.metadata import SchemaMetadataResponse
from app.schemas.metadata import LLMModelAliasItem, LLMModelAliasesResponse
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
