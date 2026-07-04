"""Liveness / readiness endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "epis-kg-api"}


@router.get("/ready")
async def ready(request: Request) -> dict:
    """Check Neo4j connectivity."""
    driver = getattr(request.app.state, "driver", None)
    if driver is None:
        return {"status": "ready", "neo4j": "demo-mode"}
    try:
        await driver.verify_connectivity()
        return {"status": "ready", "neo4j": "up"}
    except Exception as exc:  # noqa: BLE001
        return {"status": "degraded", "neo4j": "down", "error": str(exc)}
