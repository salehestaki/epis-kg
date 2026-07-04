from graph_layer.credibility import compute_source_credibility


def test_supported_source_outranks_contradicted_source():
    # s_good: two claims, both supported by evidence, never contradicted.
    # s_bad:  two claims, no evidence, both contradicted.
    source_by_claim = {"c1": "s_good", "c2": "s_good", "c3": "s_bad", "c4": "s_bad"}
    evidence_by_claim = {"c1": ["e1"], "c2": ["e2"], "c3": [], "c4": []}
    contradiction_targets = ["c3", "c4"]

    cred = compute_source_credibility(source_by_claim, evidence_by_claim, contradiction_targets)
    assert cred["s_good"] > cred["s_bad"]
    for v in cred.values():
        assert 0.0 <= v <= 1.0


def test_shared_evidence_creates_endorsement_flow():
    # s_a and s_b corroborate via shared evidence e1; s_c is isolated & contradicted.
    source_by_claim = {"c1": "s_a", "c2": "s_b", "c3": "s_c"}
    evidence_by_claim = {"c1": ["e1"], "c2": ["e1"], "c3": []}
    contradiction_targets = ["c3"]
    cred = compute_source_credibility(source_by_claim, evidence_by_claim, contradiction_targets)
    assert cred["s_a"] > cred["s_c"]
    assert cred["s_b"] > cred["s_c"]


def test_empty_input():
    assert compute_source_credibility({}, {}, []) == {}
