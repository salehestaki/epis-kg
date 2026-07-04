# ---------------------------------------------------------------------------
# Epis-KG one-command DEMO launcher (Windows / PowerShell).
#
#   ./run-demo.ps1
#
# Runs the API in EPIS_DEMO_MODE (an in-memory misinformation scenario scored by
# the real epistemic_math engine — no Docker / Neo4j / API keys needed) plus the
# Next.js frontend. Then open http://localhost:3000
#
# For the FULL stack (live LLM extraction into Neo4j) use `docker compose up`.
# ---------------------------------------------------------------------------
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "==> Creating Python venv and installing packages (first run only)..." -ForegroundColor Cyan
    python -m venv .venv
    & $py -m pip install --quiet --upgrade pip
    & $py -m pip install --quiet fastapi "uvicorn[standard]" neo4j redis networkx numpy pydantic structlog langgraph langchain-core tenacity httpx
    & $py -m pip install --quiet -e packages/graph_schema -e packages/epistemic_math -e packages/observability `
        -e services/graph_layer -e services/ingestion_service -e services/api_gateway -e services/agentic_reasoning
}

Write-Host "==> Starting API (demo mode) on http://localhost:8000 ..." -ForegroundColor Green
$env:EPIS_DEMO_MODE = "true"
$env:CORS_ORIGINS = "http://localhost:3000"
Start-Process -FilePath $py -ArgumentList "-m","uvicorn","api_gateway.main:app","--host","127.0.0.1","--port","8000" -WorkingDirectory $root

Write-Host "==> Installing frontend deps (first run only) and starting UI on http://localhost:3000 ..." -ForegroundColor Green
$frontend = Join-Path $root "frontend"
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Push-Location $frontend; npm install; Pop-Location
}
$env:NEXT_PUBLIC_API_BASE_URL = "http://localhost:8000"
$env:NEXT_PUBLIC_WS_URL = "ws://localhost:8000/ws/graph"
Start-Process -FilePath "npm" -ArgumentList "run","dev" -WorkingDirectory $frontend

Start-Sleep -Seconds 8
Write-Host ""
Write-Host "==================================================================" -ForegroundColor Yellow
Write-Host "  Epis-KG demo is starting. Open:  http://localhost:3000" -ForegroundColor Yellow
Write-Host "  API docs:                        http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "==================================================================" -ForegroundColor Yellow
