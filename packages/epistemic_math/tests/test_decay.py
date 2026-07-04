import math

import networkx as nx
import pytest

from epistemic_math import (
    ClaimSignals,
    EpistemicParams,
    RhetoricSignal,
    bayesian_update,
    contradiction_density,
    detect_misinformation_hubs,
    epistemic_decay,
    epistemic_integrity_score,
    rhetorical_penalty,
    temporal_penalty,
)

PARAMS = EpistemicParams()


def test_bayesian_update_moves_toward_evidence():
    base = bayesian_update(0.5, n_support=0, n_contradiction=0, params=PARAMS)
    more = bayesian_update(0.5, n_support=5, n_contradiction=0, params=PARAMS)
    fewer = bayesian_update(0.5, n_support=0, n_contradiction=5, params=PARAMS)
    assert fewer < base < more
    assert 0.0 < fewer and more < 1.0


def test_rhetorical_penalty_only_counts_active_vulnerabilities():
    inactive = [RhetoricSignal(0.9, is_active_vulnerability=False)]
    active = [RhetoricSignal(0.9, is_active_vulnerability=True)]
    assert rhetorical_penalty(inactive) == 0.0
    assert 0.0 < rhetorical_penalty(active) < 1.0


def test_rhetorical_penalty_monotonic_and_bounded():
    one = rhetorical_penalty([RhetoricSignal(0.8, True)])
    two = rhetorical_penalty([RhetoricSignal(0.8, True), RhetoricSignal(0.8, True)])
    assert one < two < 1.0


def test_contradiction_density_bounds():
    assert contradiction_density(0, 0) == 0.0
    assert contradiction_density(2, 8) == pytest.approx(0.25)
    assert contradiction_density(20, 8) == 1.0  # clamped


def test_temporal_penalty_grows_with_age():
    assert temporal_penalty(0, PARAMS) == 0.0
    assert temporal_penalty(10, PARAMS) < temporal_penalty(100, PARAMS) < 1.0


def test_epistemic_decay_is_weighted_sum():
    signals = ClaimSignals(
        a_priori_credibility=0.5,
        contradictions_in_degree=1,
        total_degree=4,
        age_days=10,
        rhetoric=[RhetoricSignal(0.85, True)],
    )
    d = epistemic_decay(signals, PARAMS)
    expected = (
        PARAMS.alpha * rhetorical_penalty(signals.rhetoric)
        + PARAMS.beta * contradiction_density(1, 4)
        + PARAMS.gamma * temporal_penalty(10, PARAMS)
    )
    assert d == pytest.approx(expected)


def test_eis_degrades_with_manipulation():
    clean = ClaimSignals(a_priori_credibility=0.8, n_support=3, total_degree=3)
    eroded = ClaimSignals(
        a_priori_credibility=0.8,
        n_support=3,
        contradictions_in_degree=5,
        total_degree=8,
        age_days=60,
        rhetoric=[RhetoricSignal(1.0, True), RhetoricSignal(0.85, True)],
    )
    clean_eis = epistemic_integrity_score(clean, PARAMS)
    eroded_eis = epistemic_integrity_score(eroded, PARAMS)
    assert 0.0 < eroded_eis < clean_eis <= 1.0


def test_eis_matches_closed_form():
    signals = ClaimSignals(
        a_priori_credibility=0.6, n_support=2, contradictions_in_degree=1, total_degree=5
    )
    posterior = bayesian_update(0.6, 2, 1, PARAMS)
    expected = posterior * math.exp(-epistemic_decay(signals, PARAMS))
    assert epistemic_integrity_score(signals, PARAMS) == pytest.approx(expected)


def test_detect_hubs_flags_degraded_bridge():
    # Barbell: two clusters joined by a single bridge node "bridge".
    g = nx.barbell_graph(5, 0)
    mapping = {n: f"n{n}" for n in g.nodes}
    g = nx.relabel_nodes(g, mapping)
    # Nodes 4 and 5 are the bridge in a barbell_graph(5,0).
    integrity = {n: 0.9 for n in g.nodes}
    integrity["n4"] = 0.1  # degraded bridge
    reports = detect_misinformation_hubs(g, integrity, integrity_threshold=0.4)
    flagged = {r.node_id for r in reports if r.is_active_hub}
    assert "n4" in flagged


def test_detect_hubs_empty_graph():
    assert detect_misinformation_hubs(nx.Graph(), {}) == []
