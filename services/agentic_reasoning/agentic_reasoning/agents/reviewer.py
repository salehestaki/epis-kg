"""ReviewerAgent: assemble and validate the ExtractionResult.

This is the deterministic quality gate. It coerces the agents' raw JSON into
strongly-typed Pydantic models and checks referential integrity. Any failure
is reported back into the state so the graph can loop to extraction.
"""

from __future__ import annotations

from pydantic import ValidationError

from agentic_reasoning.state import ReasoningState
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
from observability import get_logger, traced

_log = get_logger("reasoning.reviewer")

_VALID_CATEGORIES = {c.value for c in RhetoricCategory}


class ReviewerAgent:
    """Validates the assembled graph against the ontology contract."""

    @traced("agent.reviewer")
    async def __call__(self, state: ReasoningState) -> dict:
        errors: list[str] = []
        doc_payload = state["document"]

        document = Document(
            id=doc_payload.id, url=doc_payload.url, content=doc_payload.content
        )
        source = Source(
            id=f"src_{doc_payload.source_name}".replace(" ", "_"),
            name=doc_payload.source_name,
            platform=doc_payload.source_platform,
            a_priori_credibility=(
                doc_payload.a_priori_credibility
                if doc_payload.a_priori_credibility is not None
                else 0.5
            ),
        )

        claims: list[Claim] = []
        for raw in state.get("claims", []):
            try:
                claims.append(
                    Claim(
                        id=str(raw["id"]),
                        statement=str(raw["statement"]),
                        confidence=float(raw.get("confidence", 0.5)),
                    )
                )
            except (KeyError, ValidationError, ValueError, TypeError) as exc:
                errors.append(f"invalid claim {raw!r}: {exc}")

        evidence: list[Evidence] = []
        for raw in state.get("evidence", []):
            try:
                evidence.append(
                    Evidence(
                        id=str(raw["id"]),
                        type=str(raw.get("type", "citation")),
                        reference_url=raw.get("reference_url"),
                        excerpt=raw.get("excerpt"),
                    )
                )
            except (KeyError, ValidationError, ValueError, TypeError) as exc:
                errors.append(f"invalid evidence {raw!r}: {exc}")

        rhetoric: list[Rhetoric] = []
        for raw in state.get("rhetoric", []):
            category = raw.get("category")
            if category not in _VALID_CATEGORIES:
                errors.append(
                    f"rhetoric '{raw.get('id')}' has invalid category {category!r}; "
                    f"must be one of the allowed Rhetoric categories"
                )
                continue
            try:
                rhetoric.append(
                    Rhetoric(
                        id=str(raw["id"]),
                        category=RhetoricCategory(category),
                        severity_weight=raw.get("severity_weight"),
                        evidence_span=raw.get("evidence_span"),
                    )
                )
            except (KeyError, ValidationError, ValueError, TypeError) as exc:
                errors.append(f"invalid rhetoric {raw!r}: {exc}")

        contradictions: list[ClaimContradiction] = []
        for raw in state.get("contradictions", []):
            try:
                contradictions.append(
                    ClaimContradiction(
                        source_claim_id=str(raw["source_claim_id"]),
                        target_claim_id=str(raw["target_claim_id"]),
                        rationale=raw.get("rationale"),
                        semantic_distance=raw.get("semantic_distance"),
                    )
                )
            except (KeyError, ValidationError, ValueError, TypeError) as exc:
                errors.append(f"invalid contradiction {raw!r}: {exc}")

        # At least one claim is required for a useful document.
        if not claims:
            errors.append("no valid claims extracted")

        result = ExtractionResult(
            document=document,
            source=source,
            claims=claims,
            evidence=evidence,
            rhetoric=rhetoric,
            contains=[c.id for c in claims],
            supported_by=_clean_edge_map(state.get("supported_by", {})),
            decontextualizes=_clean_edge_map(state.get("decontextualizes", {})),
            employs_rhetoric=[r.id for r in rhetoric],
            contradictions=contradictions,
        )

        errors.extend(result.validate_referential_integrity())
        valid = not errors
        _log.info(
            "review",
            doc=document.id,
            valid=valid,
            errors=len(errors),
            attempt=state.get("attempts", 0),
        )
        return {"result": result, "errors": errors, "valid": valid}


def _clean_edge_map(raw: dict) -> dict[str, list[str]]:
    cleaned: dict[str, list[str]] = {}
    if not isinstance(raw, dict):
        return cleaned
    for k, v in raw.items():
        if isinstance(v, list):
            cleaned[str(k)] = [str(x) for x in v]
        elif v is not None:
            cleaned[str(k)] = [str(v)]
    return cleaned
