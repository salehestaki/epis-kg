"""Bayesian optimisation of the decay hyperparameters against LIAR.

Usage:
    python -m evaluation.tune_parameters --trials 100 --limit 400

Runs the reasoning pipeline once over the LIAR *validation* split to cache
per-claim signals, then uses Optuna (TPE Bayesian optimisation) to find the
(alpha, beta, gamma, lambda, prior_strength) that maximise the Pearson
correlation between the EIS and ground-truth veracity. Writes the winning
weights to epistemic_math/tuned_params.json, which config.load_params() then
picks up automatically.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from epistemic_math import EpistemicParams
from evaluation.env import load_dotenv
from evaluation.liar import load_liar
from evaluation.metrics import compute_report
from evaluation.pipeline import ScoredSample, collect_signals, score_with_params
from observability import configure_logging, get_logger

_log = get_logger("evaluation.tune")


def _tuned_params_path() -> Path:
    import epistemic_math

    return Path(epistemic_math.__file__).parent / "tuned_params.json"


def _objective(trial, samples: list[ScoredSample]):  # noqa: ANN001
    params = EpistemicParams(
        alpha=trial.suggest_float("alpha", 0.0, 1.5),
        beta=trial.suggest_float("beta", 0.0, 1.5),
        gamma=trial.suggest_float("gamma", 0.0, 1.0),
        lambda_=trial.suggest_float("lambda_", 0.0, 0.3),
        prior_strength=trial.suggest_float("prior_strength", 0.5, 12.0),
    )
    preds, truths = score_with_params(samples, params)
    if len(preds) < 2:
        return -1.0
    return compute_report(preds, truths).pearson_r


def main() -> None:
    load_dotenv()
    configure_logging()
    ap = argparse.ArgumentParser(description="Tune Epis-KG decay weights with Optuna")
    ap.add_argument("--trials", type=int, default=100)
    ap.add_argument("--limit", type=int, default=400)
    ap.add_argument("--split", default="validation")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    import optuna

    rows = load_liar(split=args.split, limit=args.limit)
    _log.info("caching_signals", rows=len(rows))
    samples = collect_signals(rows, concurrency=args.concurrency)
    if len(samples) < 2:
        raise SystemExit("not enough scored samples — check LLM credentials")

    study = optuna.create_study(direction="maximize", study_name="epis-kg-decay")
    study.optimize(lambda t: _objective(t, samples), n_trials=args.trials)

    best = study.best_params
    best_r = study.best_value
    out = _tuned_params_path()
    out.write_text(json.dumps({**best, "pearson_r": best_r}, indent=2), encoding="utf-8")

    print(json.dumps({"best_params": best, "pearson_r": best_r, "saved_to": str(out)}, indent=2))
    _log.info("tuning_complete", pearson_r=best_r, saved_to=str(out))


if __name__ == "__main__":
    main()
