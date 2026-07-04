"""Read-side graph queries and epistemic metric computation."""

from __future__ import annotations

import networkx as nx
from neo4j import AsyncDriver

from api_gateway.schemas import (
    GraphEdge,
    GraphNode,
    GraphResponse,
    HubResponse,
    MetricsResponse,
)
from epistemic_math import detect_misinformation_hubs
from observability import get_logger, traced

_log = get_logger("api.graph_service")

_TOPOLOGY_CYPHER = """
MATCH (n)
WHERE n:Document OR n:Source OR n:Claim OR n:Evidence OR n:Rhetoric
OPTIONAL MATCH (n)-[r]->(m)
WHERE m:Document OR m:Source OR m:Claim OR m:Evidence OR m:Rhetoric
RETURN
  collect(DISTINCT {id: n.id, label: head(labels(n)), props: properties(n)}) AS nodes,
  collect(DISTINCT CASE WHEN r IS NULL THEN NULL ELSE
    {id: toString(id(r)), source: startNode(r).id, target: endNode(r).id,
     type: type(r), props: properties(r)} END) AS edges
LIMIT 1
"""

_COUNTS_CYPHER = """
CALL {
  MATCH (n) WHERE n:Document OR n:Source OR n:Claim OR n:Evidence OR n:Rhetoric
  RETURN head(labels(n)) AS label, count(*) AS c
}
RETURN collect({label: label, c: c}) AS node_counts
"""

_EDGE_COUNTS_CYPHER = """
MATCH ()-[r]->()
RETURN type(r) AS type, count(*) AS c
"""

_EIS_CYPHER = """
MATCH (c:Claim)
RETURN avg(c.epistemic_integrity_score) AS mean_eis, count(c) AS n
"""


class GraphService:
    def __init__(self, driver: AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    @traced("graph_service.topology")
    async def topology(self, limit: int = 500) -> GraphResponse:
        """Return the graph as nodes + edges for the frontend to render."""
        async with self._driver.session(database=self._database) as session:
            record = await (await session.run(_TOPOLOGY_CYPHER)).single()
        if record is None:
            return GraphResponse(nodes=[], edges=[])

        nodes = [
            GraphNode(id=n["id"], label=n["label"], properties=_clean(n["props"]))
            for n in record["nodes"]
            if n and n.get("id") is not None
        ][:limit]
        node_ids = {n.id for n in nodes}
        edges = [
            GraphEdge(
                id=e["id"],
                source=e["source"],
                target=e["target"],
                type=e["type"],
                properties=_clean(e["props"]),
            )
            for e in record["edges"]
            if e and e.get("source") in node_ids and e.get("target") in node_ids
        ]
        return GraphResponse(nodes=nodes, edges=edges)

    @traced("graph_service.metrics")
    async def metrics(self, top_hubs: int = 10) -> MetricsResponse:
        node_counts: dict[str, int] = {}
        edge_counts: dict[str, int] = {}
        mean_eis: float | None = None
        contradiction_edges = 0

        async with self._driver.session(database=self._database) as session:
            rec = await (await session.run(_COUNTS_CYPHER)).single()
            if rec:
                node_counts = {row["label"]: row["c"] for row in rec["node_counts"]}
            async for row in await session.run(_EDGE_COUNTS_CYPHER):
                edge_counts[row["type"]] = row["c"]
            contradiction_edges = edge_counts.get("CONTRADICTS", 0)
            eis_rec = await (await session.run(_EIS_CYPHER)).single()
            if eis_rec and eis_rec["mean_eis"] is not None:
                mean_eis = float(eis_rec["mean_eis"])

        hubs = await self._hubs(top_hubs)
        return MetricsResponse(
            node_counts=node_counts,
            edge_counts=edge_counts,
            mean_epistemic_integrity=mean_eis,
            contradiction_edges=contradiction_edges,
            active_misinformation_hubs=hubs,
        )

    @traced("graph_service.hubs")
    async def _hubs(self, top_n: int) -> list[HubResponse]:
        """Build the claim/source projection and detect Active Misinformation Hubs."""
        topo = await self.topology(limit=5000)
        g = nx.Graph()
        meta: dict[str, tuple[str, str | None]] = {}
        integrity: dict[str, float] = {}
        for node in topo.nodes:
            if node.label not in ("Claim", "Source"):
                continue
            g.add_node(node.id)
            meta[node.id] = (node.label, node.properties.get("name"))
            if node.label == "Claim":
                score = node.properties.get("epistemic_integrity_score")
                if score is not None:
                    integrity[node.id] = float(score)
        for edge in topo.edges:
            if edge.source in g and edge.target in g:
                g.add_edge(edge.source, edge.target)

        if g.number_of_nodes() == 0:
            return []

        reports = detect_misinformation_hubs(g, integrity)
        out: list[HubResponse] = []
        for r in reports[:top_n]:
            label, name = meta.get(r.node_id, ("Claim", None))
            out.append(
                HubResponse(
                    node_id=r.node_id,
                    label=label,
                    name=name,
                    betweenness=round(r.betweenness, 4),
                    epistemic_integrity_score=round(r.epistemic_integrity_score, 4),
                    is_active_hub=r.is_active_hub,
                )
            )
        return out


def _clean(props: dict) -> dict:
    """Strip embeddings and truncate long content before shipping to the client."""
    cleaned: dict = {}
    for key, value in (props or {}).items():
        if key == "embedding":
            continue
        if key == "content" and isinstance(value, str) and len(value) > 500:
            cleaned[key] = value[:500] + "…"
        else:
            cleaned[key] = value
    return cleaned
