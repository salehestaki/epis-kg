"""Prior-ablation study over ALREADY-CACHED extraction signals (no LLM calls).

The base benchmark scores each claim with a neutral Bayesian prior (0.5). LIAR,
however, ships each speaker's credit history — exactly the source-credibility
signal the model's prior is designed to carry. This script re-scores the cached
signals under four conditions to isolate the contribution of the prior:

    A) neutral prior      + default weights   (content-only baseline)
    B) speaker-credibility prior + default weights
    C) speaker-credibility prior + Optuna-tuned weights (tuned on validation)

Because it reuses cached signals it costs nothing and is fully reproducible.

    python -m evaluation.ablation --signals-dir artifacts/benchmark_YYYYmmdd_HHMMSS
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from epistemic_math import EpistemicParams, load_params
from evaluation.liar import load_liar
from evaluation.metrics import compute_report, compute_report_with_ci
from evaluation.pipeline import score_with_params
from evaluation.signals_io import load_signals
from observability import configure_logging, get_logger

_log = get_logger("evaluation.ablation")


def _prior_map(split: str) -> dict[str, float]:
    return {r["statement"]: r["prior_credibility"] for r in load_liar(split=split)}


def _tune(val_samples, priors, trials: int) -> EpistemicParams:  # noqa: ANN001
    import optuna

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    def objective(trial):  # noqa: ANN001
        params = EpistemicParams(
            alpha=trial.suggest_float("alpha", 0.0, 1.5),
            beta=trial.suggest_float("beta", 0.0, 1.5),
            gamma=trial.suggest_float("gamma", 0.0, 1.0),
            lambda_=trial.suggest_float("lambda_", 0.0, 0.3),
            prior_strength=trial.suggest_float("prior_strength", 0.5, 12.0),
        )
        preds, truths = score_with_params(val_samples, params, priors=priors)
        if len(preds) < 2:
            return -1.0
        return compute_report(preds, truths).pearson_r

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=trials)
    return EpistemicParams(**study.best_params)


def _fmt_ci(ci) -> str:  # noqa: ANN001
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "n/a"


def main() -> None:
    configure_logging()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser(description="Prior-ablation on cached signals")
    ap.add_argument("--signals-dir", required=True)
    ap.add_argument("--trials", type=int, default=60)
    ap.add_argument("--n-boot", type=int, default=1000)
    args = ap.parse_args()

    d = Path(args.signals_dir)
    test = load_signals(d / "signals_test.json")
    val = load_signals(d / "signals_validation.json")
    test_priors = _prior_map("test")
    val_priors = _prior_map("validation")

    coverage = sum(1 for s in test if s.statement in test_priors) / max(len(test), 1)
    _log.info("ablation_start", test=len(test), val=len(val), prior_coverage=round(coverage, 3))

    default = load_params()

    def evaluate(params, *, neutral=False, priors=None):  # noqa: ANN001
        preds, truths = score_with_params(test, params, priors=priors, neutral_prior=neutral)
        return compute_report_with_ci(preds, truths, n_boot=args.n_boot)

    rep_a = evaluate(default, neutral=True)
    rep_b = evaluate(default, priors=test_priors)
    tuned = _tune(val, val_priors, args.trials)
    rep_c = evaluate(tuned, priors=test_priors)

    conditions = {
        "A_neutral_default": {"weights": "default", **rep_a.to_dict()},
        "B_credibility_default": {"weights": "default", **rep_b.to_dict()},
        "C_credibility_tuned": {
            "weights": {
                "alpha": tuned.alpha,
                "beta": tuned.beta,
                "gamma": tuned.gamma,
                "lambda_": tuned.lambda_,
                "prior_strength": tuned.prior_strength,
            },
            **rep_c.to_dict(),
        },
    }
    out = {"prior_coverage": coverage, "conditions": conditions}
    (d / "ablation.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    (d / "ABLATION.md").write_text(_markdown(out), encoding="utf-8")

    for name, rep in [("A neutral/default", rep_a), ("B cred/default", rep_b), ("C cred/tuned", rep_c)]:
        _log.info("ablation_condition", condition=name, pearson=round(rep.pearson_r, 3),
                  auc=round(rep.auc_roc, 3))
    print(_markdown(out))


def _markdown(out: dict) -> str:
    c = out["conditions"]

    def row(label, k):  # noqa: ANN001
        r = c[k]
        return (
            f"| {label} | {r['pearson_r']:.3f} {_fmt_ci(r.get('pearson_ci95'))} | "
            f"{r['spearman_r']:.3f} | {r['auc_roc']:.3f} {_fmt_ci(r.get('auc_ci95'))} | {r['n']} |"
        )

    t = c["C_credibility_tuned"]["weights"]
    return "\n".join(
        [
            "# Epis-KG — Prior Ablation (LIAR test split)",
            "",
            "Isolating the contribution of the Bayesian source-credibility prior. "
            "All conditions reuse the SAME cached LLM extractions (no re-running), "
            f"prior coverage = {out['prior_coverage']:.1%} of test statements.",
            "",
            "| Condition | Pearson r (95% CI) | Spearman ρ | AUC-ROC (95% CI) | n |",
            "|---|---|---|---|---|",
            row("A · neutral prior + default weights", "A_neutral_default"),
            row("B · speaker-credibility prior + default weights", "B_credibility_default"),
            row("C · speaker-credibility prior + tuned weights", "C_credibility_tuned"),
            "",
            "Tuned weights (C), selected on the validation split under the "
            f"credibility prior: α={t['alpha']:.3f}, β={t['beta']:.3f}, "
            f"γ={t['gamma']:.3f}, λ={t['lambda_']:.3f}, prior_strength={t['prior_strength']:.2f}.",
            "",
            "**Reading:** condition A is the content-only EIS (rhetoric-driven "
            "only, since isolated LIAR statements have no evidence/contradiction "
            "graph). B/C add the speaker's historical credibility as the Bayesian "
            "prior — standard, non-leaking LIAR metadata (counts exclude the "
            "current statement). This is an honest ablation: numbers are whatever "
            "the data yields, computed only on schema-valid extractions.",
            "",
        ]
    )


if __name__ == "__main__":
    main()
