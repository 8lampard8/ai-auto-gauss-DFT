#!/usr/bin/env bash
# Run the backend (uvicorn, :8000) and frontend (vite, :5173) concurrently.
# Vite proxies /api -> :8000, so open http://localhost:5173 in the browser.
set -euo pipefail
cd "$(dirname "$0")"

echo "[dev] backend  -> http://localhost:8000  (docs at /docs)"
echo "[dev] frontend -> http://localhost:5173"

(
  cd backend
  exec uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
) &
BACK=$!

(
  cd frontend
  exec npm run dev
) &
FRONT=$!

trap 'kill $BACK $FRONT 2>/dev/null || true' EXIT INT TERM
wait
