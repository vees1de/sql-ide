#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REMOTE_HOST="${REMOTE_HOST:-193.187.92.116}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/sqlide}"
REMOTE_BACKEND_DIR="${REMOTE_BACKEND_DIR:-$REMOTE_APP_DIR/backend}"
REMOTE_SERVICE="${REMOTE_SERVICE:-sqlide-backend.service}"

if ! command -v ssh >/dev/null 2>&1; then
  echo "ssh is required" >&2
  exit 1
fi

echo "Syncing backend to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_BACKEND_DIR}"
git -C "$ROOT_DIR" ls-files -z -- backend/app backend/pyproject.toml backend/README.md \
  | tar --null -T - -cf - \
  | ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p '${REMOTE_BACKEND_DIR}' && tar -xf - -C '${REMOTE_APP_DIR}'"

ssh "${REMOTE_USER}@${REMOTE_HOST}" "set -e
cd '${REMOTE_BACKEND_DIR}'
if [ ! -x .venv/bin/python3 ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip >/dev/null
.venv/bin/pip install -e . >/dev/null
systemctl restart '${REMOTE_SERVICE}'
systemctl --no-pager --full status '${REMOTE_SERVICE}' | sed -n '1,80p'
"
