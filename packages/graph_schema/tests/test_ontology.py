from graph_schema import (
    Claim,
    ClaimContradiction,
    Document,
    Evidence,
    ExtractionResult,
    Rhetoric,
    RhetoricCategory,
    Source,
    build_graph_schema,
    schema_prompt_fragment,
)
from graph_schema.ontology import RHETORIC_SEVERITY


def _minimal_result() -> ExtractionResult:
    return ExtractionResult(
        document=Document(id="d1", content="hello world"),
        source=Source(id="s1", name="Anon", a_priori_credibility=0.4),
        claims=[Claim(id="c1", statement="X causes Y")],
        evidence=[Evidence(id="e1", type="citation")],
        rhetoric=[Rhetoric(id="r1", category=RhetoricCategory.APPEAL_TO_FEAR)],
        contains=["c1"],
        supported_by={"c1": ["e1"]},
        employs_rhetoric=["r1"],
    )


def test_rhetoric_severity_defaults_from_taxonomy():
    r = Rhetoric(id="r1", category=RhetoricCategory.FABRICATION)
    assert r.severity_weight == RHETORIC_SEVERITY[RhetoricCategory.FABRICATION]
    assert r.is_active_vulnerability is True


def test_rhetoric_explicit_weight_wins():
    r = Rhetoric(id="r1", category=RhetoricCategory.HYPERBOLE, severity_weight=0.9)
    assert r.severity_weight == 0.9


def test_unit_interval_bounds_enforced():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Claim(id="c", statement="s", epistemic_integrity_score=1.5)


def test_referential_integrity_valid():
    assert _minimal_result().validate_referential_integrity() == []


def test_referential_integrity_flags_dangling_edges():
    result = _minimal_result()
    result.contradictions.append(
        ClaimContradiction(source_claim_id="c1", target_claim_id="ghost")
    )
    errors = result.validate_referential_integrity()
    assert any("ghost" in e for e in errors)


def test_graph_schema_projection_is_closed():
    schema = build_graph_schema()
    assert schema["additional_node_types"] is False
    assert {nt["label"] for nt in schema["node_types"]} == {
        "Document",
        "Source",
        "Claim",
        "Evidence",
        "Rhetoric",
    }


def test_schema_prompt_fragment_mentions_patterns_and_categories():
    frag = schema_prompt_fragment()
    assert "CONTRADICTS" in frag
    assert "Appeal to Fear" in frag
