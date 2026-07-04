"""The epistemic decay penalty and the Epistemic Integrity Score (EIS).

Epistemic erosion accelerates when a claim relies increasingly on rhetorical
amplification rather than factual replication, or when the volume of
contradictory nodes rises over time. The decay modifier ``D`` is a composite
penalty combining qualitative rhetorical analysis with quantitative graph
metrics:

    D = alpha * R  +  beta * C  +  gamma * T

where

    R = 1 - exp(-Σ_r  w_r * 1_active(r))     (rhetorical amplification, bounded)
    C = contradictions_in_degree / total_degree   (structural contradiction density)
    T = 1 - exp(-lambda * age_days)          (temporal staleness, BEWA half-life)

The final Epistemic Integrity Score maps the Bayesian posterior belief through
the erosion penalty:

    EIS = P_posterior * exp(-D)     ∈ (0, 1]

All three penalty terms live in [0, 1], so D ∈ [0, alpha+beta+gamma] and the EIS
is a monotonically decreasing function of every vector of misinformation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from epistemic_math.bayesian import bayesian_update
from epistemic_math.config import EpistemicParams


@dataclass(frozen=True, slots=True)
class RhetoricSignal:
    """One rhetorical device structurally connected to a claim's document.

    ``severity_weight`` is w_r; ``is_active_vulnerability`` is the indicator
    function 1_active(r).
    """

    severity_weight: float
    is_active_vulnerability: bool


@dataclass(slots=True)
class ClaimSignals:
    """All quantities needed to score a single claim."""

    a_priori_credibility: float
    n_support: int = 0
    contradictions_in_degree: int = 0
    total_degree: int = 0
    age_days: float = 0.0
    rhetoric: list[RhetoricSignal] = field(default_factory=list)


def rhetorical_penalty(rhetoric: list[RhetoricSignal]) -> float:
    """R ∈ [0, 1): saturating sum of active rhetorical severity weights."""
    raw = sum(r.severity_weight for r in rhetoric if r.is_active_vulnerability)
    return 1.0 - math.exp(-raw)


def contradiction_density(contradictions_in_degree: int, total_degree: int) -> float:
    """C ∈ [0, 1]: fraction of a claim's connections that are contradictions."""
    if total_degree <= 0:
        return 0.0
    return min(contradictions_in_degree / total_degree, 1.0)


def temporal_penalty(age_days: float, params: EpistemicParams) -> float:
    """T ∈ [0, 1): exponential staleness of an uncorroborated assertion."""
    age = max(age_days, 0.0)
    return 1.0 - math.exp(-params.lambda_ * age)


def epistemic_decay(signals: ClaimSignals, params: EpistemicParams) -> float:
    """Composite decay modifier D ≥ 0."""
    r = rhetorical_penalty(signals.rhetoric)
    c = contradiction_density(signals.contradictions_in_degree, signals.total_degree)
    t = temporal_penalty(signals.age_days, params)
    return params.alpha * r + params.beta * c + params.gamma * t


def epistemic_integrity_score(signals: ClaimSignals, params: EpistemicParams) -> float:
    """Final EIS ∈ (0, 1] for a claim.

    Combines the Bayesian posterior belief (evidence vs. contradiction) with the
    exponential erosion penalty derived from rhetoric, contradiction density and
    temporal staleness.
    """
    posterior = bayesian_update(
        signals.a_priori_credibility,
        signals.n_support,
        signals.contradictions_in_degree,
        params,
    )
    d = epistemic_decay(signals, params)
    eis = posterior * math.exp(-d)
    return min(max(eis, 0.0), 1.0)
