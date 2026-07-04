"""Network-driven a-priori source credibility (TrustRank / PageRank).

Hardcoding ``a_priori_credibility`` per source does not scale. Instead we derive
it from graph structure:

* **Seed quality** (personalisation vector): a source is seeded higher when more
  of its claims are ``SUPPORTED_BY`` evidence and lower when more of its claims
  are the target of ``CONTRADICTS`` edges.
* **Endorsement graph** (trust flow): two sources whose claims cite the *same*
  evidence corroborate one another, forming edges along which trust propagates.

A personalised PageRank over that graph yields a dynamic ``pagerank_credibility``
in [0, 1] for every ``Source``. The Bayesian belief update then anchors on this
instead of static metadata.

The pure computation (:func:`compute_source_credibility`) is decoupled from
Neo4j so it is unit-tested without a database; :class:`CredibilityService`
gathers the structure via Cypher and persists the result.
"""

from __future__ import annotations

from itertools import combinations

import networkx as nx
from neo4j import AsyncDriver

from observability import get_logger, traced

_log = get_logger("graph_layer.credibility")


def compute_source_credibility(
    source_by_claim: dict[str, str],
    evidence_by_claim: dict[str, list[str]],
    contradiction_targets: list[str],
    *,
    damping: float = 0.85,
    lo: float = 0.05,
    hi: float = 0.95,
) -> dict[str, float]:
    """Return ``{source_id: credibility}`` in [lo, hi].

    Parameters
    ----------
    source_by_claim:
        claim_id -> source_id (who published each claim).
    evidence_by_claim:
        claim_id -> list of evidence_ids the claim is SUPPORTED_BY.
    contradiction_targets:
        claim_ids that are the *target* of a CONTRADICTS edge.
    """
    sources = sorted(set(source_by_claim.values()))
    if not sources:
        return {}

    # --- seed quality per source ------------------------------------------
    supported: dict[str, int] = {s: 0 for s in sources}
    contradicted: dict[str, int] = {s: 0 for s in sources}
    total: dict[str, int] = {s: 0 for s in sources}
    contra_set = set(contradiction_targets)
    for claim_id, src in source_by_claim.items():
        total[src] += 1
        if evidence_by_claim.get(claim_id):
            supported[src] += 1
        if claim_id in contra_set:
            contradicted[src] += 1

    seed: dict[str, float] = {}
    for s in sources:
        n = max(total[s], 1)
        quality = 0.5 + 0.5 * (supported[s] - contradicted[s]) / n
        seed[s] = min(max(quality, 0.01), 0.99)
    seed_sum = sum(seed.values())
    personalization = {s: seed[s] / seed_sum for s in sources}

    # --- endorsement graph: shared-evidence corroboration -----------------
    g = nx.DiGraph()
    g.add_nodes_from(sources)
    evidence_to_sources: dict[str, set[str]] = {}
    for claim_id, evs in evidence_by_claim.items():
        src = source_by_claim.get(claim_id)
        if src is None:
            continue
        for ev in evs:
            evidence_to_sources.setdefault(ev, set()).add(src)
    for srcs in evidence_to_sources.values():
        for a, b in combinations(sorted(srcs), 2):
            if a == b:
                continue
            for u, v in ((a, b), (b, a)):
                if g.has_edge(u, v):
                    g[u][v]["weight"] += 1.0
                else:
                    g.add_edge(u, v, weight=1.0)

    # --- personalised PageRank -------------------------------------------
    if g.number_of_edges() == 0:
        ranks = dict(seed)  # no trust flow — fall back to seed quality
    else:
        ranks = _personalized_pagerank(g, personalization, damping)

    # --- normalise to [lo, hi] -------------------------------------------
    vals = list(ranks.values())
    vmin, vmax = min(vals), max(vals)
    span = (vmax - vmin) or 1.0
    return {s: lo + (hi - lo) * (ranks[s] - vmin) / span for s in sources}


def _personalized_pagerank(
    g: "nx.DiGraph",
    personalization: dict[str, float],
    damping: float,
    *,
    max_iter: int = 100,
    tol: float = 1e-8,
) -> dict[str, float]:
    """Pure power-iteration personalised PageRank (no scipy dependency)."""
    nodes = list(g.nodes())
    n = len(nodes)
    if n == 0:
        return {}
    rank = {v: personalization.get(v, 1.0 / n) for v in nodes}
    out_weight = {v: sum(d.get("weight", 1.0) for _, _, d in g.out_edges(v, data=True)) for v in nodes}
    dangling = [v for v in nodes if out_weight[v] == 0.0]

    for _ in range(max_iter):
        prev = rank
        rank = {v: (1.0 - damping) * personalization.get(v, 0.0) for v in nodes}
        # redistribute dangling mass by personalization
        dangling_mass = damping * sum(prev[v] for v in dangling)
        for v in nodes:
            rank[v] += dangling_mass * personalization.get(v, 0.0)
        for u in nodes:
            if out_weight[u] == 0.0:
                continue
            share = damping * prev[u] / out_weight[u]
            for _, w, d in g.out_edges(u, data=True):
                rank[w] += share * d.get("weight", 1.0)
        err = sum(abs(rank[v] - prev[v]) for v in nodes)
        if err < tol:
            break
    return rank


_GATHER_CYPHER = """
MATCH (s:Source)-[:PUBLISHED]->(:Document)-[:CONTAINS]->(c:Claim)
OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(e:Evidence)
OPTIONAL MATCH (:Claim)-[:CONTRADICTS]->(c)
RETURN c.id AS claim_id, s.id AS source_id,
       collect(DISTINCT e.id) AS evidence,
       count(DISTINCT e) AS n_ev,
       size([ (x:Claim)-[:CONTRADICTS]->(c) | 1 ]) AS contra_in
"""

_WRITE_CYPHER = """
UNWIND $rows AS row
MATCH (s:Source {id: row.id})
SET s.pagerank_credibility = row.cred
"""


class CredibilityService:
    """Compute and persist dynamic PageRank credibility for Source nodes."""

    def __init__(self, driver: AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database

    @traced("graph_layer.recompute_credibility")
    async def recompute(self) -> dict[str, float]:
        source_by_claim: dict[str, str] = {}
        evidence_by_claim: dict[str, list[str]] = {}
        contradiction_targets: list[str] = []

        async with self._driver.session(database=self._database) as session:
            async for row in await session.run(_GATHER_CYPHER):
                claim_id = row["claim_id"]
                source_by_claim[claim_id] = row["source_id"]
                evidence_by_claim[claim_id] = [e for e in row["evidence"] if e]
                if int(row["contra_in"]) > 0:
                    contradiction_targets.append(claim_id)

            credibility = compute_source_credibility(
                source_by_claim, evidence_by_claim, contradiction_targets
            )
            rows = [{"id": sid, "cred": cred} for sid, cred in credibility.items()]
            if rows:
                await session.run(_WRITE_CYPHER, rows=rows)
        _log.info("credibility_recomputed", sources=len(credibility))
        return credibility


async def main() -> None:  # pragma: no cover - operational entrypoint
    import asyncio  # noqa: F401

    from graph_layer.connection import Neo4jSettings, close_driver, get_async_driver
    from observability import configure_logging

    configure_logging()
    settings = Neo4jSettings.from_env()
    driver = get_async_driver(settings)
    try:
        result = await CredibilityService(driver, settings.database).recompute()
        print({k: round(v, 3) for k, v in result.items()})
    finally:
        await close_driver()


if __name__ == "__main__":  # pragma: no cover
    import asyncio

    asyncio.run(main())
