"""Graph-theoretic misinformation-hub detection.

Misinformation spreads through highly connected nodes that bridge otherwise
disconnected ideological clusters. We compute Betweenness Centrality (a node's
influence over information flow) and flag any node that is simultaneously a
structural bridge *and* epistemically degraded as an **Active Misinformation
Hub**.
"""

from __future__ import annotations

from dataclasses import dataclass

import networkx as nx


@dataclass(frozen=True, slots=True)
class HubReport:
    node_id: str
    betweenness: float
    epistemic_integrity_score: float
    is_active_hub: bool


def betweenness_centrality(
    graph: nx.Graph, normalized: bool = True
) -> dict[str, float]:
    """Betweenness centrality for every node.

    Accepts either a directed or undirected graph; misinformation flow is
    modelled on the undirected projection because exposure is bidirectional.
    """
    undirected = graph.to_undirected() if graph.is_directed() else graph
    return nx.betweenness_centrality(undirected, normalized=normalized)


def detect_misinformation_hubs(
    graph: nx.Graph,
    integrity: dict[str, float],
    *,
    betweenness_percentile: float = 0.90,
    integrity_threshold: float = 0.4,
) -> list[HubReport]:
    """Flag Active Misinformation Hubs.

    A node is flagged when its betweenness centrality is at/above the given
    percentile of the network *and* its Epistemic Integrity Score is at/below
    ``integrity_threshold`` (i.e. severely degraded).

    Parameters
    ----------
    graph:
        The claim/source topology.
    integrity:
        Mapping node_id -> EIS in [0, 1]. Nodes missing from this map are
        treated as fully credible (EIS = 1.0) and thus never flagged.
    betweenness_percentile:
        Fraction in (0, 1). Only nodes above this percentile qualify as bridges.
    integrity_threshold:
        EIS at/below which a node counts as degraded.
    """
    if not 0.0 < betweenness_percentile < 1.0:
        raise ValueError("betweenness_percentile must be in (0, 1)")

    centrality = betweenness_centrality(graph)
    if not centrality:
        return []

    ordered = sorted(centrality.values())
    idx = min(int(betweenness_percentile * len(ordered)), len(ordered) - 1)
    cutoff = ordered[idx]

    reports: list[HubReport] = []
    for node_id, bc in centrality.items():
        eis = integrity.get(node_id, 1.0)
        is_hub = bc >= cutoff and bc > 0.0 and eis <= integrity_threshold
        reports.append(
            HubReport(
                node_id=node_id,
                betweenness=bc,
                epistemic_integrity_score=eis,
                is_active_hub=is_hub,
            )
        )
    reports.sort(key=lambda r: (not r.is_active_hub, -r.betweenness))
    return reports
