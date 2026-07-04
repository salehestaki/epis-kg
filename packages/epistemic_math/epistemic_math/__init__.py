"""Formal computational-epistemology engine for Epis-KG.

Everything here is deterministic and unit-tested so that "epistemic worsening"
is a mathematically quantifiable metric rather than an opaque LLM judgement.

Modules
-------
config      : tunable hyperparameters (alpha, beta, gamma, lambda).
bayesian    : prior anchoring + Beta-Bernoulli belief update.
decay       : the composite epistemic decay penalty and integrity score.
centrality  : betweenness centrality and Active Misinformation Hub detection.
"""

from epistemic_math.bayesian import bayesian_update, prior_from_source
from epistemic_math.centrality import (
    HubReport,
    betweenness_centrality,
    detect_misinformation_hubs,
)
from epistemic_math.config import EpistemicParams, load_params
from epistemic_math.decay import (
    ClaimSignals,
    RhetoricSignal,
    contradiction_density,
    epistemic_integrity_score,
    epistemic_decay,
    rhetorical_penalty,
    temporal_penalty,
)

__all__ = [
    "EpistemicParams",
    "load_params",
    "prior_from_source",
    "bayesian_update",
    "ClaimSignals",
    "RhetoricSignal",
    "rhetorical_penalty",
    "contradiction_density",
    "temporal_penalty",
    "epistemic_decay",
    "epistemic_integrity_score",
    "betweenness_centrality",
    "detect_misinformation_hubs",
    "HubReport",
]
