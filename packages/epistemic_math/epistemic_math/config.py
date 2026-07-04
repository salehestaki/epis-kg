"""Tunable hyperparameters for the epistemic model.

The α, β, γ weights let researchers adjust the model's relative sensitivity to
emotional manipulation, logical contradiction, and temporal staleness. λ is the
exponential temporal-decay constant (per day) from the BEWA framework.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class EpistemicParams:
    alpha: float = 0.5   # sensitivity to rhetorical manipulation
    beta: float = 0.35   # sensitivity to contradiction density
    gamma: float = 0.15  # sensitivity to temporal staleness
    lambda_: float = 0.05  # temporal decay constant (per day)
    # Strength (pseudo-count) of the source's a-priori credibility as a prior.
    prior_strength: float = 4.0

    def __post_init__(self) -> None:
        for name in ("alpha", "beta", "gamma", "lambda_", "prior_strength"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must be non-negative")


def _tuned_params() -> dict[str, float]:
    """Load Optuna-tuned weights if a tuned_params.json is present.

    Written by ``evaluation.tune_parameters``. The path can be overridden with
    ``EPIS_TUNED_PARAMS``; otherwise we look next to this module.
    """
    path = os.getenv("EPIS_TUNED_PARAMS")
    candidate = Path(path) if path else Path(__file__).with_name("tuned_params.json")
    if not candidate.exists():
        return {}
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
        return {k: float(v) for k, v in data.items() if k in _FIELDS}
    except Exception:  # noqa: BLE001 - never let a bad file break scoring
        return {}


_FIELDS = ("alpha", "beta", "gamma", "lambda_", "prior_strength")
_DEFAULTS = {"alpha": 0.5, "beta": 0.35, "gamma": 0.15, "lambda_": 0.05, "prior_strength": 4.0}
_ENV_KEYS = {
    "alpha": "EPIS_ALPHA",
    "beta": "EPIS_BETA",
    "gamma": "EPIS_GAMMA",
    "lambda_": "EPIS_LAMBDA",
    "prior_strength": "EPIS_PRIOR_STRENGTH",
}


def load_params() -> EpistemicParams:
    """Load hyperparameters.

    Precedence (highest first): environment variables > tuned_params.json >
    built-in defaults. This lets Optuna-optimised weights ship in the repo while
    still allowing per-deployment overrides via the environment.
    """
    values = dict(_DEFAULTS)
    values.update(_tuned_params())
    for field_name, env_key in _ENV_KEYS.items():
        raw = os.getenv(env_key)
        if raw not in (None, ""):
            values[field_name] = float(raw)
    return EpistemicParams(**values)
