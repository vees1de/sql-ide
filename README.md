# SQL IDE

Notebook-first AI analytics workspace для кейса по NL-to-SQL.

## Что уже есть

- [backend/README.md](/Users/vees1de/repos/sql-ide/backend/README.md) - описание backend MVP и запуск
- [PLAN.md](/Users/vees1de/repos/sql-ide/PLAN.md) - продуктовый и архитектурный план
- `db-samples/` - входные sample datasets
- `test/test_db.py` и `test/test_api.py` - smoke tests для `dvdrental` и Yandex AI

## Backend

В `backend/` собран FastAPI backend по плану:

- workspaces / notebooks / cells / reports / semantic dictionary
- orchestration pipeline `intent -> semantic -> SQL -> validation -> execution -> visualization -> insight`
- LLM path для OpenAI-compatible API с fallback на rule-based pipeline
- SQL safety через whitelist и `sqlglot`
- встроенная demo analytics database для локального MVP
- backend читает и `backend/.env`, и корневой `.env`, поэтому ключ из `test/test_api.py` можно переиспользовать без дублирования

Команда запуска:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload
```

Для запуска против локального `dvdrental` используйте:

```bash
ANALYTICS_DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/dvdrental
```
## SQL IDE

Notebook-first аналитическая среда: `Vue 3` frontend + `FastAPI` backend + `PostgreSQL`.

### Что работает

- frontend больше не использует моковый store и ходит в реальный backend API
- backend поднимается на `FastAPI`, хранит notebooks/reports в PostgreSQL и seeds demo notebooks
- аналитическая demo-база тоже живёт в PostgreSQL
- prompt composer на фронте вызывает реальный `POST /api/notebooks/{id}/prompt-runs`

### Быстрый старт

1. Поднять PostgreSQL и backend:

```bash
docker compose up --build -d postgres backend
```

2. Запустить frontend:

```bash
cd frontend
npm install
npm run dev
```

3. Открыть приложение:

- frontend: `http://127.0.0.1:5173`
- backend API: `http://127.0.0.1:8001`
- backend docs: `http://127.0.0.1:8001/docs`
- PostgreSQL host port: `5433`

### Полезно знать

- `frontend` в dev-режиме проксирует `/api` на `http://127.0.0.1:8001`
- если нужен другой backend URL, задайте `VITE_API_BASE_URL` или `VITE_PROXY_TARGET`
- compose использует две PostgreSQL базы:
  - `sqlide_service`
  - `sqlide_analytics`
