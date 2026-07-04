#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Epis-KG one-command DEMO launcher (macOS / Linux / Git Bash).
#
#   ./run-demo.sh
#
# Runs the API in EPIS_DEMO_MODE (an in-memory misinformation scenario scored by
# the real epistemic_math engine — no Docker / Neo4j / API keys needed) plus the
# Next.js frontend. Then open http://localhost:3000
#
# For the FULL stack (live LLM extraction into Neo4j) use `docker compose up`.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")"

PY=".venv/bin/python"
[ -f "$PY" ] || PY=".venv/Scripts/python.exe"   # Git Bash on Windows

if [ ! -f "$PY" ]; then
  echo "==> Creating Python venv and installing packages (first run only)..."
  python -m venv .venv
  PY=".venv/bin/python"; [ -f "$PY" ] || PY=".venv/Scripts/python.exe"
  "$PY" -m pip install --quiet --upgrade pip
  "$PY" -m pip install --quiet fastapi "uvicorn[standard]" neo4j redis networkx numpy pydantic structlog langgraph langchain-core tenacity httpx
  "$PY" -m pip install --quiet -e packages/graph_schema -e packages/epistemic_math -e packages/observability \
    -e services/graph_layer -e services/ingestion_service -e services/api_gateway -e services/agentic_reasoning
fi

echo "==> Starting API (demo mode) on http://localhost:8000 ..."
EPIS_DEMO_MODE=true CORS_ORIGINS="http://localhost:3000" \
  "$PY" -m uvicorn api_gateway.main:app --host 127.0.0.1 --port 8000 &
API_PID=$!

echo "==> Starting frontend on http://localhost:3000 ..."
( cd frontend && [ -d node_modules ] || npm install
  NEXT_PUBLIC_API_BASE_URL="http://localhost:8000" \
  NEXT_PUBLIC_WS_URL="ws://localhost:8000/ws/graph" npm run dev ) &
FRONT_PID=$!

trap 'kill $API_PID $FRONT_PID 2>/dev/null || true' INT TERM
echo ""
echo "=================================================================="
echo "  Epis-KG demo running. Open:  http://localhost:3000"
echo "  API docs:                    http://localhost:8000/docs"
echo "  Press Ctrl+C to stop."
echo "=================================================================="
wait
