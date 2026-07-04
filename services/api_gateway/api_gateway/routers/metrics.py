"""Epistemic metrics endpoint: counts, mean integrity, misinformation hubs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api_gateway.dependencies import get_graph_service
from api_gateway.graph_service import GraphService
from api_gateway.schemas import MetricsResponse

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", response_model=MetricsResponse)
async def get_metrics(
    top_hubs: int = Query(10, ge=1, le=50),
    service: GraphService = Depends(get_graph_service),
) -> MetricsResponse:
    return await service.metrics(top_hubs=top_hubs)
