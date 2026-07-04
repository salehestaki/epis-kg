"""Multi-model consensus utilities for hallucination mitigation.

When two independent LLMs are asked to extract atomic claims / rhetoric, an item
that appears in *both* outputs is far less likely to be a hallucination. We
intersect the two extractions: claims are matched by semantic similarity of
their statements, rhetoric by category. Only agreed items survive.

Semantic matching uses ``difflib`` so no embedding model / extra dependency is
required at runtime; the threshold is tunable via ``EPIS_CONSENSUS_THRESHOLD``.
"""

from __future__ import annotations

import os
from difflib import SequenceMatcher


def _norm(text: str) -> str:
    return " ".join(str(text).lower().split())


def _similar(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def consensus_threshold() -> float:
    try:
        return float(os.getenv("EPIS_CONSENSUS_THRESHOLD", "0.6"))
    except ValueError:
        return 0.6


def agree_claims(
    claims_a: list[dict], claims_b: list[dict], threshold: float | None = None
) -> list[dict]:
    """Keep claims from A that have a semantically-similar counterpart in B."""
    thr = threshold if threshold is not None else consensus_threshold()
    b_statements = [str(c.get("statement", "")) for c in claims_b]
    kept: list[dict] = []
    for c in claims_a:
        stmt = str(c.get("statement", ""))
        if any(_similar(stmt, bs) >= thr for bs in b_statements):
            kept.append(c)
    return kept


def agree_rhetoric(rhetoric_a: list[dict], rhetoric_b: list[dict]) -> list[dict]:
    """Keep rhetoric from A whose category also appears in B (exact category)."""
    b_categories = {str(r.get("category", "")).lower() for r in rhetoric_b}
    return [r for r in rhetoric_a if str(r.get("category", "")).lower() in b_categories]
