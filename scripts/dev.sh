#!/usr/bin/env bash
# Local development helper
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Backend (port 8000)"
cd "$ROOT/backend"
if [[ ! -d .venv ]]; then
  uv venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uv pip install -e ".[dev]"
else
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi
uvicorn app.main:app --reload --port 8000 &
BACK_PID=$!

echo "==> Frontend (port 5173)"
cd "$ROOT/frontend"
[[ -d node_modules ]] || npm install
npm run dev &
FRONT_PID=$!

trap 'kill $BACK_PID $FRONT_PID 2>/dev/null || true' EXIT
wait
