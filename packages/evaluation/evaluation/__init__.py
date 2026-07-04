"""Empirical evaluation and hyperparameter tuning for Epis-KG.

* :mod:`evaluation.liar` - load and label-map the LIAR fact-checking dataset.
* :mod:`evaluation.pipeline` - run statements through the reasoning pipeline and
  collect per-claim decay *signals* (the expensive step, run once).
* :mod:`evaluation.evaluate_eis` - correlation / AUC-ROC of EIS vs ground truth.
* :mod:`evaluation.tune_parameters` - Optuna Bayesian optimisation of the decay
  weights against the LIAR validation split (reusing cached signals).
"""

from evaluation.liar import LABEL_TO_SCORE, load_liar
from evaluation.pipeline import ScoredSample, collect_signals, score_with_params

__all__ = [
    "LABEL_TO_SCORE",
    "load_liar",
    "ScoredSample",
    "collect_signals",
    "score_with_params",
]
