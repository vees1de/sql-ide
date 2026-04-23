#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${REMOTE_HOST:-193.187.92.116}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/sqlide}"
REMOTE_DB_DIR="${REMOTE_DB_DIR:-$REMOTE_APP_DIR/train-db}"
REMOTE_CONTAINER_NAME="${REMOTE_CONTAINER_NAME:-sqlide-train-postgres}"
REMOTE_VOLUME_NAME="${REMOTE_VOLUME_NAME:-sqlide-train-db-data}"
DB_USER="${DB_USER:-trainuser}"
DB_PASSWORD="${DB_PASSWORD:-Tr4in!8888A9}"
DB_NAME="${DB_NAME:-train_db}"
DB_PORT="${DB_PORT:-8888}"

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh is required" >&2
  exit 1
fi

ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p '${REMOTE_DB_DIR}'"

tar -C "$ROOT_DIR/db-samples" -cf - train.csv load_train.py \
  | ssh "${REMOTE_USER}@${REMOTE_HOST}" "tar -xf - -C '${REMOTE_DB_DIR}'"

ssh "${REMOTE_USER}@${REMOTE_HOST}" "set -e
docker volume create '${REMOTE_VOLUME_NAME}' >/dev/null
docker rm -f '${REMOTE_CONTAINER_NAME}' >/dev/null 2>&1 || true
docker run -d \
  --name '${REMOTE_CONTAINER_NAME}' \
  --restart unless-stopped \
  -e POSTGRES_USER='${DB_USER}' \
  -e POSTGRES_PASSWORD='${DB_PASSWORD}' \
  -e POSTGRES_DB='${DB_NAME}' \
  -p 0.0.0.0:${DB_PORT}:5432 \
  -v '${REMOTE_VOLUME_NAME}':/var/lib/postgresql/data \
  postgres:16-alpine >/dev/null

ufw allow ${DB_PORT}/tcp >/dev/null 2>&1 || true

until docker exec '${REMOTE_CONTAINER_NAME}' pg_isready -U '${DB_USER}' -d '${DB_NAME}' >/dev/null 2>&1; do
  sleep 1
done

cd '${REMOTE_DB_DIR}'
DATABASE_URL='postgresql://${DB_USER}:${DB_PASSWORD}@127.0.0.1:${DB_PORT}/${DB_NAME}' \
  /opt/sqlide/backend/.venv/bin/python load_train.py

docker exec '${REMOTE_CONTAINER_NAME}' psql -U '${DB_USER}' -d '${DB_NAME}' -c 'SELECT COUNT(*) AS train_rows FROM train;'
"

echo "Train DB deployed on ${REMOTE_HOST}:${DB_PORT}"
echo "Login: ${DB_USER}"
echo "Password: ${DB_PASSWORD}"
echo "Host: ${REMOTE_HOST}"
echo "Database: ${DB_NAME}"
