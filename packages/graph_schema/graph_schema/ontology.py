"""Pydantic models describing the Epis-KG epistemic ontology.

The ontology maps the journey of information from its *source*, through the
discrete *claims* it makes, to the *rhetoric* used to persuade the reader and
the *evidence* marshalled (or misused) to support it. These models are used
to (a) constrain the LLM's structured output during extraction and (b) type
the payloads that flow between services.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

# --------------------------------------------------------------------------- #
# Controlled vocabularies
# --------------------------------------------------------------------------- #


class NodeLabel(str, Enum):
    """The five node labels permitted in the graph."""

    DOCUMENT = "Document"
    SOURCE = "Source"
    CLAIM = "Claim"
    EVIDENCE = "Evidence"
    RHETORIC = "Rhetoric"


class RelationshipType(str, Enum):
    """The directed edges that define the topological tension of the network."""

    PUBLISHED = "PUBLISHED"                  # Source      -> Document
    CONTAINS = "CONTAINS"                    # Document    -> Claim
    SUPPORTED_BY = "SUPPORTED_BY"            # Claim       -> Evidence
    CONTRADICTS = "CONTRADICTS"              # Claim       -> Claim
    DECONTEXTUALIZES = "DECONTEXTUALIZES"    # Claim       -> Evidence
    EMPLOYS_RHETORIC = "EMPLOYS_RHETORIC"    # Document    -> Rhetoric


class RhetoricCategory(str, Enum):
    """Taxonomy of logical fallacies and emotional-manipulation markers.

    ``severity_weight`` in :class:`Rhetoric` should be seeded from
    :data:`RHETORIC_SEVERITY` unless the reasoning layer overrides it.
    """

    # Emotional manipulation
    APPEAL_TO_FEAR = "Appeal to Fear"
    APPEAL_TO_EMOTION = "Appeal to Emotion"
    APPEAL_TO_OUTRAGE = "Appeal to Outrage"
    LOADED_LANGUAGE = "Loaded Language"
    # Logical fallacies
    AD_HOMINEM = "Ad Hominem"
    STRAWMAN = "Strawman"
    FALSE_DILEMMA = "False Dilemma"
    SLIPPERY_SLOPE = "Slippery Slope"
    HASTY_GENERALIZATION = "Hasty Generalization"
    APPEAL_TO_AUTHORITY = "Appeal to (False) Authority"
    WHATABOUTISM = "Whataboutism"
    CIRCULAR_REASONING = "Circular Reasoning"
    # Epistemic corruption
    DECONTEXTUALIZATION = "Decontextualization"
    CHERRY_PICKING = "Cherry Picking"
    FABRICATION = "Fabrication"
    HYPERBOLE = "Hyperbole"


#: Default severity weights in [0, 1]. Fabrication / Ad Hominem penalise more
#: heavily than mild hyperbole. Consumed by the epistemic decay function.
RHETORIC_SEVERITY: dict[RhetoricCategory, float] = {
    RhetoricCategory.FABRICATION: 1.0,
    RhetoricCategory.AD_HOMINEM: 0.85,
    RhetoricCategory.DECONTEXTUALIZATION: 0.85,
    RhetoricCategory.CHERRY_PICKING: 0.8,
    RhetoricCategory.STRAWMAN: 0.75,
    RhetoricCategory.FALSE_DILEMMA: 0.7,
    RhetoricCategory.APPEAL_TO_FEAR: 0.7,
    RhetoricCategory.APPEAL_TO_OUTRAGE: 0.65,
    RhetoricCategory.WHATABOUTISM: 0.6,
    RhetoricCategory.SLIPPERY_SLOPE: 0.6,
    RhetoricCategory.CIRCULAR_REASONING: 0.6,
    RhetoricCategory.HASTY_GENERALIZATION: 0.55,
    RhetoricCategory.APPEAL_TO_AUTHORITY: 0.5,
    RhetoricCategory.LOADED_LANGUAGE: 0.5,
    RhetoricCategory.APPEAL_TO_EMOTION: 0.45,
    RhetoricCategory.HYPERBOLE: 0.3,
}

#: Rhetoric categories that constitute an *active epistemic vulnerability*
#: (the indicator function `1_active` in the decay model).
ACTIVE_VULNERABILITIES: frozenset[RhetoricCategory] = frozenset(
    {
        RhetoricCategory.FABRICATION,
        RhetoricCategory.DECONTEXTUALIZATION,
        RhetoricCategory.APPEAL_TO_FEAR,
        RhetoricCategory.CHERRY_PICKING,
        RhetoricCategory.STRAWMAN,
        RhetoricCategory.FALSE_DILEMMA,
    }
)


UnitInterval = Annotated[float, Field(ge=0.0, le=1.0)]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Node models
# --------------------------------------------------------------------------- #


class Source(BaseModel):
    """The origin entity of a document (author, user, or publication)."""

    id: str = Field(..., description="Stable unique identifier for the source.")
    name: str
    platform: str | None = Field(None, description="e.g. X, Reddit, NYTimes")
    a_priori_credibility: UnitInterval = Field(
        0.5,
        description="Historical/authoritative credibility, independent of the "
        "network. Used as the Bayesian prior anchor for its claims.",
    )


class Document(BaseModel):
    """A raw ingested text, article, or social-media thread."""

    id: str
    url: str | None = None
    content: str
    timestamp: datetime = Field(default_factory=_utcnow)


class Evidence(BaseModel):
    """Data, citations, or URLs referenced to back (or misused to back) a claim."""

    id: str
    type: str = Field("citation", description="citation | statistic | quote | url")
    reference_url: str | None = None
    excerpt: str | None = None


class Rhetoric(BaseModel):
    """An emotional trigger or logical fallacy deployed in the text."""

    id: str
    category: RhetoricCategory
    # None means "use the taxonomy default for this category" (resolved below).
    severity_weight: UnitInterval | None = Field(
        default=None,
        description="Penalisation weight. Defaults to RHETORIC_SEVERITY[category].",
    )
    evidence_span: str | None = Field(
        None, description="The text span that triggered detection."
    )

    @model_validator(mode="after")
    def _default_from_category(self) -> "Rhetoric":
        # If the caller did not supply a weight, fall back to the taxonomy default.
        if self.severity_weight is None:  # type: ignore[comparison-overlap]
            object.__setattr__(
                self, "severity_weight", RHETORIC_SEVERITY.get(self.category, 0.5)
            )
        return self

    @property
    def is_active_vulnerability(self) -> bool:
        return self.category in ACTIVE_VULNERABILITIES


class Claim(BaseModel):
    """A discrete, atomic assertion extracted from a document."""

    id: str
    statement: str
    confidence: UnitInterval = Field(
        0.5, description="Extractor confidence that this is a faithful atomic claim."
    )
    epistemic_integrity_score: UnitInterval = Field(
        0.5,
        description="Network-induced integrity in [0,1]. Computed by the "
        "epistemic_math layer, not by the LLM.",
    )
    created_at: datetime = Field(default_factory=_utcnow)


# --------------------------------------------------------------------------- #
# Relationship / extraction payloads
# --------------------------------------------------------------------------- #


class ClaimContradiction(BaseModel):
    """A CONTRADICTS edge asserted between two claims within a batch."""

    source_claim_id: str
    target_claim_id: str
    rationale: str | None = None
    semantic_distance: UnitInterval | None = Field(
        None, description="1 - cosine similarity between claim embeddings."
    )


class ExtractionResult(BaseModel):
    """The full structured payload produced by the reasoning layer for one document.

    This is exactly the JSON contract the ReviewerAgent validates before the
    graph writer is allowed to persist anything.
    """

    document: Document
    source: Source
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    rhetoric: list[Rhetoric] = Field(default_factory=list)

    # edges expressed as id references
    contains: list[str] = Field(
        default_factory=list, description="Claim ids contained in the document."
    )
    supported_by: dict[str, list[str]] = Field(
        default_factory=dict, description="claim_id -> [evidence_id, ...]"
    )
    decontextualizes: dict[str, list[str]] = Field(
        default_factory=dict, description="claim_id -> [evidence_id, ...]"
    )
    employs_rhetoric: list[str] = Field(
        default_factory=list, description="Rhetoric ids employed by the document."
    )
    contradictions: list[ClaimContradiction] = Field(default_factory=list)

    def claim_index(self) -> dict[str, Claim]:
        return {c.id: c for c in self.claims}

    def validate_referential_integrity(self) -> list[str]:
        """Return a list of human-readable integrity errors (empty == valid).

        The ReviewerAgent uses this to decide whether to loop back to
        extraction. It checks that every edge references a declared node.
        """
        errors: list[str] = []
        claim_ids = {c.id for c in self.claims}
        evidence_ids = {e.id for e in self.evidence}
        rhetoric_ids = {r.id for r in self.rhetoric}

        for cid in self.contains:
            if cid not in claim_ids:
                errors.append(f"CONTAINS references unknown claim '{cid}'")
        for cid, evs in self.supported_by.items():
            if cid not in claim_ids:
                errors.append(f"SUPPORTED_BY references unknown claim '{cid}'")
            for ev in evs:
                if ev not in evidence_ids:
                    errors.append(f"SUPPORTED_BY references unknown evidence '{ev}'")
        for cid, evs in self.decontextualizes.items():
            if cid not in claim_ids:
                errors.append(f"DECONTEXTUALIZES references unknown claim '{cid}'")
            for ev in evs:
                if ev not in evidence_ids:
                    errors.append(f"DECONTEXTUALIZES references unknown evidence '{ev}'")
        for rid in self.employs_rhetoric:
            if rid not in rhetoric_ids:
                errors.append(f"EMPLOYS_RHETORIC references unknown rhetoric '{rid}'")
        for c in self.contradictions:
            if c.source_claim_id not in claim_ids:
                errors.append(
                    f"CONTRADICTS references unknown source claim '{c.source_claim_id}'"
                )
            if c.target_claim_id not in claim_ids:
                errors.append(
                    f"CONTRADICTS references unknown target claim '{c.target_claim_id}'"
                )
        return errors
