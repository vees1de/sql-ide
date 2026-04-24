#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${REMOTE_HOST:-193.187.92.116}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/sqlide}"
REMOTE_BACKEND_DIR="${REMOTE_BACKEND_DIR:-$REMOTE_APP_DIR/backend}"

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh is required" >&2
  exit 1
fi

ssh "${REMOTE_USER}@${REMOTE_HOST}" "set -e
cd '${REMOTE_BACKEND_DIR}'
.venv/bin/python - <<'PY'
from app.services.bootstrap import apply_schema_migrations

apply_schema_migrations()
PY
"
