from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


YANDEX_MODEL_ALIASES = {
    "deepseek": "deepseek-v32/latest",
    "gpt120": "gpt-oss-120b/latest",
    "gpt20": "gpt-oss-20b/latest",
    "qwen": "qwen3.5-35b-a3b-fp8/latest",
}
DEFAULT_YANDEX_FOLDER_ID = "b1gste4lfr39is20f5r8"
DEFAULT_YANDEX_MODEL_ALIAS = "gpt120"


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _read_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _read_csv(name: str, default: str) -> tuple[str, ...]:
    raw_value = os.getenv(name, default)
    return tuple(
        item.strip()
        for item in raw_value.split(",")
        if item.strip()
    )


def _read_optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _resolve_llm_api_key() -> str | None:
    return _read_optional("LLM_API_KEY") or _read_optional("YANDEX_AI_API_KEY")


def _resolve_llm_api_base_url() -> str | None:
    configured = _read_optional("LLM_API_BASE_URL") or _read_optional("YANDEX_AI_API_BASE_URL")
    if configured:
        return configured
    if _read_optional("YANDEX_AI_API_KEY"):
        return "https://ai.api.cloud.yandex.net/v1"
    return None


def _resolve_llm_model() -> str | None:
    configured = _read_optional("LLM_MODEL") or _read_optional("YANDEX_AI_MODEL") or _read_optional("YANDEX_AI_MODEL_ALIAS")
    if configured and configured.startswith("gpt://"):
        return configured

    if configured in YANDEX_MODEL_ALIASES or (configured is None and _read_optional("YANDEX_AI_API_KEY")):
        alias = configured or DEFAULT_YANDEX_MODEL_ALIAS
        folder_id = _read_optional("YANDEX_AI_FOLDER_ID") or DEFAULT_YANDEX_FOLDER_ID
        return f"gpt://{folder_id}/{YANDEX_MODEL_ALIASES[alias]}"

    return configured


def normalize_llm_model_alias(value: str | None) -> str:
    candidate = (value or "").strip().lower()
    if candidate in YANDEX_MODEL_ALIASES:
        return candidate
    return DEFAULT_YANDEX_MODEL_ALIAS


def resolve_llm_model_from_alias(alias: str | None) -> str:
    normalized_alias = normalize_llm_model_alias(alias)
    folder_id = _read_optional("YANDEX_AI_FOLDER_ID") or DEFAULT_YANDEX_FOLDER_ID
    return f"gpt://{folder_id}/{YANDEX_MODEL_ALIASES[normalized_alias]}"


def detect_llm_model_alias(model: str | None) -> str:
    normalized_model = (model or "").strip()
    if not normalized_model:
        return DEFAULT_YANDEX_MODEL_ALIAS
    lowered_model = normalized_model.lower()
    for alias, model_path in YANDEX_MODEL_ALIASES.items():
        if lowered_model == alias:
            return alias
        if normalized_model.endswith(f"/{model_path}") or normalized_model.endswith(model_path):
            return alias
    return DEFAULT_YANDEX_MODEL_ALIAS


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    api_prefix: str
    base_dir: Path
    data_dir: Path
    service_database_url: str
    analytics_database_url: str
    analytics_uses_demo_data: bool
    allowed_tables: tuple[str, ...]
    default_row_limit: int
    max_row_limit: int
    query_timeout_seconds: int
    demo_workspace_name: str
    demo_database_id: str
    demo_database_name: str
    llm_api_base_url: str | None
    llm_api_key: str | None
    llm_model: str | None
    mail_smtp_key: str | None
    mail_smtp_host: str | None
    mail_smtp_port: int
    mail_smtp_user: str | None
    mail_from_address: str | None
    cors_allow_origins: tuple[str, ...]


def get_settings() -> Settings:
    base_dir = Path(__file__).resolve().parents[2]
    repo_dir = base_dir.parent
    _load_env_file(base_dir / ".env")
    _load_env_file(repo_dir / ".env")
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    demo_analytics_path = data_dir / "analytics_demo.db"
    service_db_path = data_dir / "service.db"

    analytics_database_url = os.getenv("ANALYTICS_DATABASE_URL", "").strip()
    uses_demo_data = not analytics_database_url
    if uses_demo_data:
        analytics_database_url = f"sqlite:///{demo_analytics_path}"

    service_database_url = os.getenv("SERVICE_DATABASE_URL", "").strip()
    if not service_database_url:
        service_database_url = f"sqlite:///{service_db_path}"

    allowed_tables = tuple(
        table.strip()
        for table in os.getenv("ALLOWED_TABLES", "").split(",")
        if table.strip()
    )

    return Settings(
        app_name=os.getenv("APP_NAME", "SQL IDE Backend"),
        environment=os.getenv("ENVIRONMENT", "development"),
        api_prefix=os.getenv("API_PREFIX", "/api"),
        base_dir=base_dir,
        data_dir=data_dir,
        service_database_url=service_database_url,
        analytics_database_url=analytics_database_url,
        analytics_uses_demo_data=uses_demo_data or _read_bool("BOOTSTRAP_DEMO_ANALYTICS", False),
        allowed_tables=allowed_tables,
        default_row_limit=int(os.getenv("DEFAULT_ROW_LIMIT", "50")),
        max_row_limit=int(os.getenv("MAX_ROW_LIMIT", "1000")),
        query_timeout_seconds=int(os.getenv("QUERY_TIMEOUT_SECONDS", "15")),
        demo_workspace_name=os.getenv("DEMO_WORKSPACE_NAME", "Demo Workspace"),
        demo_database_id=os.getenv("DEMO_DATABASE_ID", "demo_analytics"),
        demo_database_name=os.getenv("DEMO_DATABASE_NAME", "Demo Analytics DB"),
        llm_api_base_url=_resolve_llm_api_base_url(),
        llm_api_key=_resolve_llm_api_key(),
        llm_model=_resolve_llm_model(),
        mail_smtp_key=_read_optional("MAIL_SMTP_KEY"),
        mail_smtp_host=_read_optional("MAIL_SMTP_HOST") or _read_optional("SMTP_HOST"),
        mail_smtp_port=int(os.getenv("MAIL_SMTP_PORT", os.getenv("SMTP_PORT", "587"))),
        mail_smtp_user=_read_optional("MAIL_SMTP_USER") or _read_optional("SMTP_USER"),
        mail_from_address=_read_optional("MAIL_FROM_ADDRESS") or _read_optional("SMTP_FROM_ADDRESS"),
        cors_allow_origins=_read_csv(
            "CORS_ALLOW_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://localhost:4173",
        ),
    )


settings = get_settings()
