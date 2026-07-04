from agentic_reasoning.consensus import agree_claims, agree_rhetoric


def test_agree_claims_keeps_semantically_matching():
    a = [
        {"id": "c1", "statement": "The water supply is contaminated with toxins"},
        {"id": "c2", "statement": "The mayor was born in 1970"},  # only in A
    ]
    b = [
        {"id": "x1", "statement": "the water supply is contaminated with toxins"},
    ]
    kept = agree_claims(a, b, threshold=0.6)
    ids = {c["id"] for c in kept}
    assert "c1" in ids
    assert "c2" not in ids  # hallucinated-by-one claim dropped


def test_agree_claims_threshold_strictness():
    a = [{"id": "c1", "statement": "climate change is accelerating"}]
    b = [{"id": "x1", "statement": "the weather is nice today"}]
    assert agree_claims(a, b, threshold=0.6) == []


def test_agree_rhetoric_matches_on_category():
    a = [
        {"id": "r1", "category": "Appeal to Fear"},
        {"id": "r2", "category": "Hyperbole"},
    ]
    b = [{"id": "y1", "category": "appeal to fear"}]
    kept = agree_rhetoric(a, b)
    assert [r["id"] for r in kept] == ["r1"]
