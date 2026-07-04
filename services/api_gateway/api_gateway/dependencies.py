"""Shared FastAPI dependencies wired from app.state."""

from __future__ import annotations

from fastapi import Request

from api_gateway.graph_service import GraphService
from api_gateway.retrievers import Text2CypherService, VectorCypherService
from ingestion_service.broker import RedisStreamBroker


def get_graph_service(request: Request) -> GraphService:
    return request.app.state.graph_service


def get_text2cypher(request: Request) -> Text2CypherService:
    return request.app.state.text2cypher


def get_vector_cypher(request: Request) -> VectorCypherService:
    return request.app.state.vector_cypher


def get_broker(request: Request) -> RedisStreamBroker:
    return request.app.state.broker
