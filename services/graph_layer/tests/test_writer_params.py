"""Unit tests for the pure (non-DB) parts of the graph writer."""

from graph_layer.writer import EpistemicGraphWriter, _age_days, _category_is_active
from graph_schema import (
    Claim,
    ClaimContradiction,
    Document,
    Evidence,
    ExtractionResult,
    Rhetoric,
    RhetoricCategory,
    Source,
)


def _writer() -> EpistemicGraphWriter:
    # The driver is never touched by _to_cypher_params.
    return EpistemicGraphWriter(driver=None)  # type: ignore[arg-type]


def _result() -> ExtractionResult:
    return ExtractionResult(
        document=Document(id="d1", content="text", url="http://x"),
        source=Source(id="s1", name="Anon", a_priori_credibility=0.3),
        claims=[Claim(id="c1", statement="A"), Claim(id="c2", statement="B")],
        evidence=[Evidence(id="e1", type="citation")],
        rhetoric=[Rhetoric(id="r1", category=RhetoricCategory.FABRICATION)],
        contains=["c1", "c2"],
        supported_by={"c1": ["e1"]},
        decontextualizes={"c2": ["e1"]},
        employs_rhetoric=["r1"],
        contradictions=[ClaimContradiction(source_claim_id="c1", target_claim_id="c2")],
    )


def test_to_cypher_params_flattens_edges():
    params = _writer()._to_cypher_params(_result())
    assert params["supported_by"] == [{"claim_id": "c1", "evidence_id": "e1"}]
    assert params["decontextualizes"] == [{"claim_id": "c2", "evidence_id": "e1"}]
    assert params["rhetoric"][0]["category"] == "Fabrication"
    assert params["contradictions"][0]["source_claim_id"] == "c1"
    # timestamps serialised to ISO strings
    assert isinstance(params["document"]["timestamp"], str)


def test_category_is_active():
    assert _category_is_active("Fabrication") is True
    assert _category_is_active("Hyperbole") is False
    assert _category_is_active("not-a-category") is False


def test_age_days_handles_missing_and_naive():
    assert _age_days(None) == 0.0
    assert _age_days("garbage") == 0.0
    assert _age_days("2020-01-01T00:00:00") > 0.0
