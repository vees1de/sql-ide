# SQL IDE Backend

Backend MVP для notebook-first аналитики из `PLAN.md`.

## Что внутри

- `FastAPI` API для workspaces, notebooks, reports, semantic dictionary и metadata
- агентный pipeline: `intent -> semantic -> SQL -> validation -> execution -> visualization -> insight`
- LLM path для OpenAI-compatible API с fallback на rule-based pipeline
- read-only execution layer для аналитической БД
- встроенный demo analytics database на `SQLite`, чтобы проект запускался без внешнего PostgreSQL
- сервисная БД для notebooks, cells, query history и reports
- поддержка `PostgreSQL` для сервисной и аналитической БД

## Быстрый старт

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

После старта документация будет доступна на:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## Docker Compose

Из корня репозитория:

```bash
docker compose up --build -d postgres backend
```

Тогда:

- backend будет доступен на `http://127.0.0.1:8001`
- PostgreSQL будет доступен на `127.0.0.1:5433`
- сервисная БД: `sqlide_service`
- аналитическая БД: `sqlide_analytics`

## Конфигурация

Скопируйте `.env.example` в `.env` и при необходимости переопределите значения.
Backend читает и `backend/.env`, и корневой `.env`, поэтому можно использовать тот же `YANDEX_AI_API_KEY`, что и в `test/test_api.py`.

- `SERVICE_DATABASE_URL` - сервисная БД notebook-приложения
- `ANALYTICS_DATABASE_URL` - аналитическая read-only БД
- `CORS_ALLOW_ORIGINS` - разрешённые origin'ы для frontend
- `ALLOWED_TABLES` - whitelist таблиц для SQL validator
- `LLM_API_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` - опциональный внешний LLM
- `YANDEX_AI_API_KEY`, `YANDEX_AI_FOLDER_ID`, `YANDEX_AI_MODEL_ALIAS` - shortcut для Yandex AI OpenAI-compatible API

Если `ANALYTICS_DATABASE_URL` не задан, приложение поднимет demo-базу с таблицами:

- `orders`
- `customers`
- `campaigns`

Для запуска на PostgreSQL используйте строки вида:

```bash
SERVICE_DATABASE_URL=postgresql+psycopg://sqlide:sqlide@127.0.0.1:5432/sqlide_service
ANALYTICS_DATABASE_URL=postgresql+psycopg://sqlide:sqlide@127.0.0.1:5432/sqlide_analytics
EMBEDDED_ANALYTICS_ENABLED=true
```

Для локального `dvdrental` и Yandex AI из тестов:

```bash
ANALYTICS_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/dvdrental
YANDEX_AI_API_KEY=...
YANDEX_AI_FOLDER_ID=b1gste4lfr39is20f5r8
YANDEX_AI_MODEL_ALIAS=qwen
```

Проверить состояние можно через `GET /api/health`: там есть статусы сервисной БД, аналитической БД и LLM-конфига.

## Основные endpoint'ы

- `GET /api/health`
- `GET /api/workspaces`
- `GET /api/databases`
- `GET /api/notebooks`
- `POST /api/notebooks`
- `GET /api/notebooks/{notebook_id}`
- `POST /api/notebooks/{notebook_id}/prompt-runs`
- `POST /api/notebooks/{notebook_id}/run-all`
- `GET /api/notebooks/{notebook_id}/history`
- `GET /api/query-templates`
- `GET /api/reports`
- `GET /api/semantic-dictionary`
- `GET /api/metadata/schema`

## Что умеет MVP

- хранить ноутбуки, ячейки, query runs и сохранённые отчёты
- понимать типовые аналитические запросы на русском и английском
- учитывать контекст предыдущего prompt в notebook
- строить безопасный `SELECT` SQL по demo-схеме или через LLM по реальной схеме БД
- автоматически выбирать chart spec и писать короткий insight
- выдавать clarification cell при неоднозначном запросе

## Eval `/chat text-to-sql`

Для агентного цикла `прогон -> оценка -> фиксы -> повторный прогон` добавлен отдельный harness:

```bash
python backend/scripts/eval_chat_text_to_sql.py \
  --cases backend/evals/chat_text_to_sql_suite.json \
  --api-base http://127.0.0.1:8000/api \
  --fail-under 0.85
```

Что делает harness:

- гоняет реальные запросы через `POST /api/chat/...`
- отдельно оценивает `clarification / understanding`, `sql`, `chart`
- при необходимости выполняет сгенерированный SQL через `/execute`
- пишет машинно-читаемые артефакты:
  - `results.json`
  - `summary.json`
  - `failing_steps.json`
  - `repair_brief.md`

Suite-файл хранится в JSON и поддерживает multi-turn кейсы, ожидания по `intent`, SQL-паттернам, результату выполнения и chart recommendation. Это удобно давать LLM-агенту как вход для автоматического улучшения `backend/app/services/llm_service.py`, `backend/app/services/chat_sql_adapter.py`, `backend/app/agents/semantic.py`, `backend/app/services/chart_decision_service.py` и связанных частей пайплайна.

Подробный пошаговый гайд:

- [backend/evals/README.md](/Users/vees1de/repos/sql-ide/backend/evals/README.md)
