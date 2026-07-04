"""Request/response models for the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, examples=[
        "Which claims about the water supply have the lowest epistemic integrity?"
    ])
    top_k: int = Field(10, ge=1, le=100)
    # text2cypher = analytical/aggregate queries; vector = semantic context lookup.
    retriever: Literal["text2cypher", "vector"] = "text2cypher"


class QueryResponse(BaseModel):
    question: str
    cypher: str | None = None
    answer: str
    records: list[dict]


class IngestRequest(BaseModel):
    content: str = Field(..., min_length=1)
    url: str | None = None
    source_name: str = "api"
    source_platform: str | None = None
    a_priori_credibility: float | None = Field(None, ge=0.0, le=1.0)


class IngestResponse(BaseModel):
    document_id: str
    queued_message_id: str


class GraphNode(BaseModel):
    id: str
    label: str
    properties: dict


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: dict = Field(default_factory=dict)


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class HubResponse(BaseModel):
    node_id: str
    label: str
    name: str | None = None
    betweenness: float
    epistemic_integrity_score: float
    is_active_hub: bool


class MetricsResponse(BaseModel):
    node_counts: dict[str, int]
    edge_counts: dict[str, int]
    mean_epistemic_integrity: float | None
    contradiction_edges: int
    active_misinformation_hubs: list[HubResponse]
