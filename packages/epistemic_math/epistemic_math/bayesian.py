"""Bayesian belief anchoring and update.

The core mechanism separates a *source's* a-priori credibility from a *claim's*
endogenous, network-induced confidence. We model belief in a claim's factual
validity as a Beta distribution:

    prior  ~ Beta(a0, b0),   a0 = p0 * kappa,  b0 = (1 - p0) * kappa

where ``p0`` is the source's a-priori credibility and ``kappa`` the prior
strength (how much we trust that prior before seeing the network). Supporting
evidence acts as Bernoulli "successes" and contradictions as "failures", giving
a closed-form posterior mean.
"""

from __future__ import annotations

from epistemic_math.config import EpistemicParams


def prior_from_source(a_priori_credibility: float, params: EpistemicParams) -> tuple[float, float]:
    """Return the Beta prior pseudo-counts ``(a0, b0)`` for a claim.

    ``a_priori_credibility`` is clamped to (0, 1) to keep the Beta parameters
    strictly positive.
    """
    p0 = min(max(a_priori_credibility, 1e-6), 1 - 1e-6)
    kappa = params.prior_strength
    return p0 * kappa, (1.0 - p0) * kappa


def bayesian_update(
    a_priori_credibility: float,
    n_support: int,
    n_contradiction: int,
    params: EpistemicParams,
    dynamic_credibility: float | None = None,
) -> float:
    """Posterior mean belief in the claim's validity, in (0, 1).

    Parameters
    ----------
    a_priori_credibility:
        Static credibility of the publishing source (fallback prior anchor).
    n_support:
        Count of SUPPORTED_BY evidence edges (Bernoulli successes).
    n_contradiction:
        In-degree of CONTRADICTS edges targeting the claim (failures).
    dynamic_credibility:
        Network-derived source credibility (PageRank/TrustRank). When provided
        it *overrides* the static ``a_priori_credibility`` as the prior anchor,
        so belief reflects the source's structural standing rather than
        hardcoded metadata. See ``graph_layer.credibility``.
    """
    if n_support < 0 or n_contradiction < 0:
        raise ValueError("evidence counts must be non-negative")
    anchor = dynamic_credibility if dynamic_credibility is not None else a_priori_credibility
    a0, b0 = prior_from_source(anchor, params)
    a = a0 + n_support
    b = b0 + n_contradiction
    return a / (a + b)
