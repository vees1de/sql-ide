#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$ROOT_DIR/frontend"
REMOTE_HOST="${REMOTE_HOST:-193.187.92.116}"
REMOTE_USER="${REMOTE_USER:-root}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/sqlide}"
REMOTE_FRONTEND_DIR="${REMOTE_FRONTEND_DIR:-$REMOTE_APP_DIR/frontend/dist}"
APP_BASE_PATH="${APP_BASE_PATH:-/x9p4k2q7/}"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required" >&2
  exit 1
fi

cd "$FRONTEND_DIR"
npm ci
VITE_APP_BASE="$APP_BASE_PATH" npm run build

echo "Syncing frontend dist to ${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_FRONTEND_DIR}"
ssh "${REMOTE_USER}@${REMOTE_HOST}" "mkdir -p '${REMOTE_FRONTEND_DIR}'"
tar -C "$FRONTEND_DIR/dist" -cf - . \
  | ssh "${REMOTE_USER}@${REMOTE_HOST}" "tar -xf - -C '${REMOTE_FRONTEND_DIR}'"
