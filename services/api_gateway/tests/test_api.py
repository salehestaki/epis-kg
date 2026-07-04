"""API tests with stubbed services (no live Neo4j/Redis required)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api_gateway.dependencies import get_broker, get_graph_service, get_text2cypher
from api_gateway.main import create_app
from api_gateway.schemas import (
    GraphEdge,
    GraphNode,
    GraphResponse,
    HubResponse,
    MetricsResponse,
)


class FakeGraphService:
    async def topology(self, limit: int = 500) -> GraphResponse:
        return GraphResponse(
            nodes=[
                GraphNode(id="c1", label="Claim", properties={"statement": "toxic",
                                                               "epistemic_integrity_score": 0.1}),
                GraphNode(id="s1", label="Source", properties={"name": "Anon"}),
            ],
            edges=[GraphEdge(id="e0", source="s1", target="c1", type="PUBLISHED")],
        )

    async def metrics(self, top_hubs: int = 10) -> MetricsResponse:
        return MetricsResponse(
            node_counts={"Claim": 1, "Source": 1},
            edge_counts={"PUBLISHED": 1, "CONTRADICTS": 2},
            mean_epistemic_integrity=0.1,
            contradiction_edges=2,
            active_misinformation_hubs=[
                HubResponse(node_id="c1", label="Claim", betweenness=0.9,
                            epistemic_integrity_score=0.1, is_active_hub=True)
            ],
        )


class FakeText2Cypher:
    async def search(self, question: str, top_k: int = 10):
        return "MATCH (c:Claim) RETURN c LIMIT 1", [{"content": "toxic water"}]


class FakeBroker:
    async def publish(self, doc) -> str:  # noqa: ANN001
        return "1-0"

    async def close(self) -> None:
        return None


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_graph_service] = lambda: FakeGraphService()
    app.dependency_overrides[get_text2cypher] = lambda: FakeText2Cypher()
    app.dependency_overrides[get_broker] = lambda: FakeBroker()
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_graph_topology(client: TestClient):
    resp = client.get("/graph")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["nodes"]) == 2
    assert data["edges"][0]["type"] == "PUBLISHED"


def test_metrics_reports_hub(client: TestClient):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert data["contradiction_edges"] == 2
    assert data["active_misinformation_hubs"][0]["is_active_hub"] is True


def test_query(client: TestClient):
    resp = client.post("/query", json={"question": "which claims are least credible?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["cypher"].startswith("MATCH")
    assert data["records"][0]["content"] == "toxic water"


def test_ingest(client: TestClient):
    resp = client.post("/ingest", json={"content": "some claim text", "source_name": "t"})
    assert resp.status_code == 202
    assert resp.json()["document_id"].startswith("doc_")
