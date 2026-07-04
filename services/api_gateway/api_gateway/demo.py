"""In-memory demo graph for running the UI without live Neo4j/Redis.

Enabled with ``EPIS_DEMO_MODE=true``. The scores are NOT faked: the same
``epistemic_math`` engine used in production computes each claim's Epistemic
Integrity Score and the Active Misinformation Hubs from an in-memory topology
based on the bundled water-safety misinformation scenario.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from api_gateway.schemas import (
    GraphEdge,
    GraphNode,
    GraphResponse,
    HubResponse,
    MetricsResponse,
)
from epistemic_math import (
    ClaimSignals,
    RhetoricSignal,
    detect_misinformation_hubs,
    epistemic_integrity_score,
    load_params,
)


@dataclass
class _Src:
    id: str
    name: str
    platform: str
    cred: float


@dataclass
class _Doc:
    id: str
    src: str
    content: str
    rhetoric: list[tuple[str, str, float, bool]]  # (id, category, severity, active)


@dataclass
class _Claim:
    id: str
    doc: str
    statement: str


# --- The scenario ---------------------------------------------------------- #
_SOURCES = [
    _Src("src_TruthBlaster99", "TruthBlaster99", "X", 0.15),
    _Src("src_CityWaterAuthority", "City Water Authority", "Gov", 0.85),
    _Src("src_WellnessWarrior", "WellnessWarrior", "Blog", 0.25),
    _Src("src_UniversityResearch", "University Research Group", "Journal", 0.90),
    _Src("src_FreedomVoice", "FreedomVoice", "Telegram", 0.10),
    _Src("src_FactCheckDesk", "FactCheck Desk", "News", 0.80),
]

_DOCS = [
    _Doc("d1", "src_TruthBlaster99", "Water plant secretly dumping toxic chemicals!",
         [("rh1", "Appeal to Fear", 0.7, True), ("rh2", "Fabrication", 1.0, True)]),
    _Doc("d2", "src_CityWaterAuthority", "Quarterly report: all contaminant levels within EPA limits.",
         []),
    _Doc("d3", "src_WellnessWarrior", "One study at 1000x dose means water is deadly at any dose.",
         [("rh3", "Cherry Picking", 0.8, True), ("rh4", "Ad Hominem", 0.85, False)]),
    _Doc("d4", "src_UniversityResearch", "Peer-reviewed aquifer study: seasonal variation, no exceedance.",
         []),
    _Doc("d5", "src_FreedomVoice", "Every expert is bought; the water gives you cancer in a week!",
         [("rh5", "Appeal to Fear", 0.7, True), ("rh6", "Appeal to (False) Authority", 0.5, False)]),
    _Doc("d6", "src_FactCheckDesk", "Fact-check: the toxic-dumping claim has no evidence; cited study is unrelated.",
         []),
]

_CLAIMS = [
    _Claim("c1", "d1", "The water treatment plant dumps toxic chemicals"),
    _Claim("c2", "d2", "All contaminant levels are within EPA limits"),
    _Claim("c3", "d3", "The water is deadly at any dose"),
    _Claim("c4", "d4", "There is no exceedance of safety thresholds"),
    _Claim("c5", "d5", "The water gives you cancer within a week"),
    _Claim("c6", "d6", "The toxic-dumping claim is unsupported by evidence"),
]

_EVIDENCE = [
    ("e1", "statistic", "EPA quarterly measurements"),
    ("e2", "citation", "University peer-reviewed paper"),
]

# claim -> evidence (SUPPORTED_BY)
_SUPPORTED = {"c2": ["e1"], "c4": ["e2"], "c6": ["e1"]}
# claim -> claim (CONTRADICTS)
_CONTRADICTIONS = [
    ("c1", "c2"), ("c2", "c1"),
    ("c3", "c4"), ("c4", "c3"),
    ("c5", "c2"),
    ("c1", "c6"), ("c6", "c1"),
    ("c5", "c6"),
]


def _build() -> tuple[GraphResponse, MetricsResponse]:
    params = load_params()
    src_by_id = {s.id: s for s in _SOURCES}
    doc_by_id = {d.id: d for d in _DOCS}

    # Degree bookkeeping for the epistemic math.
    contra_in: dict[str, int] = {c.id: 0 for c in _CLAIMS}
    degree: dict[str, int] = {c.id: 0 for c in _CLAIMS}
    for a, b in _CONTRADICTIONS:
        contra_in[b] += 1
        degree[a] += 1
        degree[b] += 1
    for c in _CLAIMS:
        degree[c.id] += 1  # CONTAINS edge from its document
    for cid, evs in _SUPPORTED.items():
        degree[cid] += len(evs)

    # Compute EIS per claim with the real engine.
    eis: dict[str, float] = {}
    for c in _CLAIMS:
        doc = doc_by_id[c.doc]
        src = src_by_id[doc.src]
        rhetoric = [
            RhetoricSignal(severity_weight=sev, is_active_vulnerability=active)
            for (_id, _cat, sev, active) in doc.rhetoric
        ]
        signals = ClaimSignals(
            a_priori_credibility=src.cred,
            n_support=len(_SUPPORTED.get(c.id, [])),
            contradictions_in_degree=contra_in[c.id],
            total_degree=degree[c.id],
            age_days=3.0,
            rhetoric=rhetoric,
        )
        eis[c.id] = round(epistemic_integrity_score(signals, params), 4)

    # --- Assemble nodes -------------------------------------------------- #
    nodes: list[GraphNode] = []
    for s in _SOURCES:
        nodes.append(GraphNode(id=s.id, label="Source", properties={
            "name": s.name, "platform": s.platform, "a_priori_credibility": s.cred}))
    for d in _DOCS:
        nodes.append(GraphNode(id=d.id, label="Document", properties={"content": d.content}))
    for c in _CLAIMS:
        nodes.append(GraphNode(id=c.id, label="Claim", properties={
            "statement": c.statement, "epistemic_integrity_score": eis[c.id], "confidence": 0.8}))
    for eid, etype, ref in _EVIDENCE:
        nodes.append(GraphNode(id=eid, label="Evidence", properties={"type": etype, "reference_url": ref}))
    for d in _DOCS:
        for (rid, cat, sev, _active) in d.rhetoric:
            nodes.append(GraphNode(id=rid, label="Rhetoric", properties={
                "category": cat, "severity_weight": sev}))

    # --- Assemble edges -------------------------------------------------- #
    edges: list[GraphEdge] = []
    ei = 0

    def _edge(src: str, tgt: str, typ: str) -> None:
        nonlocal ei
        edges.append(GraphEdge(id=f"e{ei}", source=src, target=tgt, type=typ))
        ei += 1

    for d in _DOCS:
        _edge(d.src, d.id, "PUBLISHED")
    for c in _CLAIMS:
        _edge(c.doc, c.id, "CONTAINS")
    for cid, evs in _SUPPORTED.items():
        for ev in evs:
            _edge(cid, ev, "SUPPORTED_BY")
    for a, b in _CONTRADICTIONS:
        _edge(a, b, "CONTRADICTS")
    for d in _DOCS:
        for (rid, _cat, _sev, _active) in d.rhetoric:
            _edge(d.id, rid, "EMPLOYS_RHETORIC")

    graph = GraphResponse(nodes=nodes, edges=edges)

    # --- Metrics --------------------------------------------------------- #
    g = nx.Graph()
    for c in _CLAIMS:
        g.add_node(c.id)
    for s in _SOURCES:
        g.add_node(s.id)
    # project claim<->claim and source->claim (via document) for centrality
    for a, b in _CONTRADICTIONS:
        g.add_edge(a, b)
    for c in _CLAIMS:
        g.add_edge(src_by_id[doc_by_id[c.doc].src].id, c.id)

    hubs_raw = detect_misinformation_hubs(g, eis, integrity_threshold=0.4)
    name_by_id = {s.id: s.name for s in _SOURCES}
    hubs = [
        HubResponse(
            node_id=h.node_id,
            label="Claim" if h.node_id.startswith("c") else "Source",
            name=name_by_id.get(h.node_id),
            betweenness=round(h.betweenness, 4),
            epistemic_integrity_score=round(h.epistemic_integrity_score, 4),
            is_active_hub=h.is_active_hub,
        )
        for h in hubs_raw[:10]
    ]

    node_counts: dict[str, int] = {}
    for n in nodes:
        node_counts[n.label] = node_counts.get(n.label, 0) + 1
    edge_counts: dict[str, int] = {}
    for e in edges:
        edge_counts[e.type] = edge_counts.get(e.type, 0) + 1
    mean_eis = round(sum(eis.values()) / len(eis), 4)

    metrics = MetricsResponse(
        node_counts=node_counts,
        edge_counts=edge_counts,
        mean_epistemic_integrity=mean_eis,
        contradiction_edges=edge_counts.get("CONTRADICTS", 0),
        active_misinformation_hubs=hubs,
    )
    return graph, metrics


class DemoGraphService:
    """Drop-in replacement for GraphService backed by the in-memory scenario."""

    def __init__(self) -> None:
        self._graph, self._metrics = _build()

    async def topology(self, limit: int = 500) -> GraphResponse:
        return self._graph

    async def metrics(self, top_hubs: int = 10) -> MetricsResponse:
        return self._metrics


class DemoRetriever:
    """Answers /query in demo mode without an LLM by scanning claim statements."""

    def __init__(self, graph: GraphResponse) -> None:
        self._claims = [n for n in graph.nodes if n.label == "Claim"]

    async def search(self, question: str, top_k: int = 10):
        q = question.lower()
        scored = sorted(
            self._claims,
            key=lambda n: float(n.properties.get("epistemic_integrity_score", 1.0)),
        )
        # naive keyword filter, else fall back to lowest-integrity claims
        matches = [n for n in scored if any(w in str(n.properties.get("statement", "")).lower()
                                            for w in q.split() if len(w) > 3)]
        chosen = (matches or scored)[:top_k]
        records = [
            {"claim": n.properties.get("statement"),
             "epistemic_integrity_score": n.properties.get("epistemic_integrity_score")}
            for n in chosen
        ]
        return "MATCH (c:Claim) RETURN c.statement, c.epistemic_integrity_score ORDER BY c.epistemic_integrity_score ASC", records
