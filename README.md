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

## Как поднять проект локально

Ниже самый практичный сценарий для разработки:

1. Поднять PostgreSQL в Docker.
2. Запустить backend локально.
3. Запустить frontend локально.
4. При необходимости развернуть тестовую БД `dvdrental`.

### 1. Поднять PostgreSQL в Docker

Из корня репозитория:

```bash
docker compose up -d postgres
```

После старта PostgreSQL будет доступен на:

- host: `127.0.0.1`
- port: `5433`
- user: `sqlide`
- password: `sqlide`

Проверка:

```bash
docker compose ps
```

### 2. Запустить backend локально

Из `backend/`:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Если хотите использовать PostgreSQL из Docker для сервисной БД и встроенной analytics DB:

```bash
export SERVICE_DATABASE_URL=postgresql+psycopg://sqlide:sqlide@127.0.0.1:5433/sqlide_service
export ANALYTICS_DATABASE_URL=postgresql+psycopg://sqlide:sqlide@127.0.0.1:5433/sqlide_analytics
export EMBEDDED_ANALYTICS_ENABLED=true
```

Если хотите запускать backend против `dvdrental`, используйте:

```bash
export SERVICE_DATABASE_URL=postgresql+psycopg://sqlide:sqlide@127.0.0.1:5433/sqlide_service
export ANALYTICS_DATABASE_URL=postgresql+psycopg://sqlide:sqlide@127.0.0.1:5433/dvdrental
```

После этого:

```bash
uvicorn app.main:app --reload
```

Backend будет доступен на:

- API: `http://127.0.0.1:8000/api`
- Swagger: `http://127.0.0.1:8000/docs`

### 3. Запустить frontend локально

Из `frontend/`:

```bash
cd frontend
npm install
npm run dev
```

Frontend будет доступен на:

- `http://127.0.0.1:5173`

По умолчанию dev frontend ходит в локальный backend через `/api`.

Если backend у вас не на стандартном порту, задайте:

```bash
export VITE_API_BASE_URL=http://127.0.0.1:8000/api
```

или настройте `VITE_PROXY_TARGET`.

## Как поднять `dvdrental`

В репозитории уже лежит дамп:

- [db-samples/dvdrental/restore.sql](/Users/vees1de/repos/sql-ide/db-samples/dvdrental/restore.sql)

и все `.dat` файлы, которые он использует.

### Вариант 1. Загрузить `dvdrental` в PostgreSQL из Docker

1. Убедитесь, что контейнер PostgreSQL уже поднят:

```bash
docker compose up -d postgres
```

2. Из корня репозитория выполните:

```bash
DVDDIR="$(pwd)/db-samples/dvdrental"
sed \
  -e "s|\$\$PATH\$\$|$DVDDIR|g" \
  -e "s|OWNER TO postgres|OWNER TO sqlide|g" \
  db-samples/dvdrental/restore.sql \
  | docker exec -i sql-ide-postgres psql -U sqlide -d postgres
```

Что делает эта команда:

- подставляет реальный путь к `.dat` файлам вместо `$$PATH$$`
- заменяет `OWNER TO postgres` на `OWNER TO sqlide`, потому что в docker-compose используется роль `sqlide`
- выполняет импорт в контейнерный PostgreSQL

3. Проверьте, что база появилась:

```bash
docker exec -it sql-ide-postgres psql -U sqlide -d postgres -c "\\l"
```

4. Быстрая проверка таблиц:

```bash
docker exec -it sql-ide-postgres psql -U sqlide -d dvdrental -c "\\dt"
```

### Вариант 2. Использовать `dvdrental` как analytics DB для backend

После импорта просто запустите backend с:

```bash
export SERVICE_DATABASE_URL=postgresql+psycopg://sqlide:sqlide@127.0.0.1:5433/sqlide_service
export ANALYTICS_DATABASE_URL=postgresql+psycopg://sqlide:sqlide@127.0.0.1:5433/dvdrental
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

### Если backend уже запущен и нужно добавить `dvdrental` через UI

Используйте подключение:

- host: `127.0.0.1`
- port: `5433`
- database: `dvdrental`
- username: `sqlide`
- password: `sqlide`

## Полезные команды

Поднять только БД в Docker:

```bash
docker compose up -d postgres
```

Поднять БД и backend в Docker:

```bash
docker compose up --build -d postgres backend
```

Остановить контейнеры:

```bash
docker compose down
```

Посмотреть логи PostgreSQL:

```bash
docker compose logs -f postgres
```

Посмотреть логи backend в Docker:

```bash
docker compose logs -f backend
```
