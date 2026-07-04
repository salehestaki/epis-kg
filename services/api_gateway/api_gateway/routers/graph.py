"""Graph topology endpoint (feeds the React Flow canvas)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api_gateway.dependencies import get_graph_service
from api_gateway.graph_service import GraphService
from api_gateway.schemas import GraphResponse

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("", response_model=GraphResponse)
async def get_graph(
    limit: int = Query(500, ge=1, le=5000),
    service: GraphService = Depends(get_graph_service),
) -> GraphResponse:
    return await service.topology(limit=limit)
