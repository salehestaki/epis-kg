"""End-to-end Q1 benchmark orchestrator.

One command runs the whole empirical study and writes a reproducible artifact
bundle suitable for a journal submission:

    python -m evaluation.benchmark --test-limit 200 --val-limit 120 --trials 80

Pipeline:
  1. Load LIAR (test + validation splits) and record label distributions.
  2. Run each statement through the reasoning pipeline ONCE, caching per-claim
     signals to disk (reused for both evaluation and tuning — no double spend).
  3. Evaluate the EIS on test with default weights (Pearson/Spearman/AUC-ROC +
     95% bootstrap CIs).
  4. Tune the decay weights on the validation split with Optuna (TPE).
  5. Re-evaluate on test with the tuned weights.
  6. Persist: signals, per-sample predictions (CSV), tuned_params.json, a JSON
     report, a human-readable REPORT.md, run metadata, and a full JSON-lines log.
"""

from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from dataclasses import asdict
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from epistemic_math import EpistemicParams, load_params
from evaluation.env import load_dotenv
from evaluation.liar import load_liar
from evaluation.metrics import compute_report_with_ci
from evaluation.pipeline import (
    PipelineStats,
    ScoredSample,
    collect_signals_with_stats,
    score_with_params,
)
from evaluation.signals_io import load_signals, save_signals
from observability import configure_logging, get_logger

_log = get_logger("evaluation.benchmark")


class RunLog:
    """Structured JSON-lines log written to disk for the record."""

    def __init__(self, path: Path) -> None:
        self._fh = path.open("w", encoding="utf-8")

    def event(self, event: str, **fields) -> None:  # noqa: ANN003
        record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()
        _log.info(event, **fields)

    def close(self) -> None:
        self._fh.close()


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _pkg_versions() -> dict[str, str]:
    import importlib.metadata as md

    out: dict[str, str] = {}
    for pkg in ("datasets", "optuna", "scikit-learn", "scipy", "numpy", "openai"):
        try:
            out[pkg] = md.version(pkg)
        except Exception:  # noqa: BLE001
            out[pkg] = "n/a"
    return out


def _collect_or_load(
    rows, signals_path: Path, stmt_cache, concurrency: int, log: RunLog, split: str,
    progress_path: Path | None = None,
) -> tuple[list[ScoredSample], PipelineStats | None]:  # noqa: ANN001
    if signals_path.exists():
        log.event("signals_cache_hit", split=split, path=str(signals_path))
        return load_signals(signals_path), None
    log.event("pipeline_start", split=split, rows=len(rows), cached=len(stmt_cache))
    t0 = time.perf_counter()
    samples, stats = collect_signals_with_stats(
        rows, concurrency=concurrency, cache=stmt_cache,
        progress_path=progress_path, label=split,
    )
    save_signals(samples, signals_path)
    log.event(
        "pipeline_done",
        split=split,
        seconds=round(time.perf_counter() - t0, 1),
        **stats.to_dict(),
    )
    return samples, stats


def _tune(val_samples: list[ScoredSample], trials: int, log: RunLog) -> tuple[EpistemicParams, float]:
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
        preds, truths = score_with_params(val_samples, params)
        if len(preds) < 2:
            return -1.0
        from evaluation.metrics import compute_report

        return compute_report(preds, truths).pearson_r

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=trials)
    best = EpistemicParams(**study.best_params)
    log.event("tuning_done", trials=trials, best_pearson=round(study.best_value, 4), **study.best_params)
    return best, study.best_value


def _label_distribution(rows) -> dict[str, int]:  # noqa: ANN001
    return dict(Counter(r["label"] for r in rows))


def main() -> None:
    ap = argparse.ArgumentParser(description="Epis-KG end-to-end LIAR benchmark")
    ap.add_argument("--test-limit", type=int, default=200)
    ap.add_argument("--val-limit", type=int, default=120)
    ap.add_argument("--trials", type=int, default=80)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--n-boot", type=int, default=1000)
    ap.add_argument("--out-dir", default="artifacts")
    ap.add_argument(
        "--min-success-rate",
        type=float,
        default=0.5,
        help="Abort (rather than report) if fewer than this fraction of LLM "
        "extractions succeed — avoids publishing numbers from a mostly-failed run.",
    )
    args = ap.parse_args()

    load_dotenv()
    configure_logging()
    try:  # Windows consoles default to cp1252; the report uses unicode (α, ρ, ≥).
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = Path(args.out_dir) / f"benchmark_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    log = RunLog(out / "run.log")

    import os

    meta = {
        "timestamp": stamp,
        "git_commit": _git_commit(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "llm_provider": os.getenv("LLM_PROVIDER", "deepseek"),
        "llm_model": os.getenv("LLM_MODEL", "deepseek-v4-flash"),
        "consensus_mode": os.getenv("EPIS_CONSENSUS_MODE", "false"),
        "packages": _pkg_versions(),
        "config": vars(args),
    }
    log.event("benchmark_start", **{k: meta[k] for k in ("llm_provider", "llm_model")}, **vars(args))

    # --- 1. dataset ------------------------------------------------------
    test_rows = load_liar(split="test", limit=args.test_limit)
    val_rows = load_liar(split="validation", limit=args.val_limit)
    meta["dataset"] = {
        "test": {"n": len(test_rows), "labels": _label_distribution(test_rows)},
        "validation": {"n": len(val_rows), "labels": _label_distribution(val_rows)},
    }
    log.event("dataset_loaded", test=len(test_rows), validation=len(val_rows))

    # --- 2. signals (the expensive pass, cached + resumable) -------------
    from evaluation.signal_cache import StatementCache

    cache_dir = Path(args.out_dir) / "_signal_cache"
    test_cache = StatementCache(cache_dir / "test.jsonl")
    val_cache = StatementCache(cache_dir / "validation.jsonl")
    progress = Path(args.out_dir) / "progress.json"  # stable path to watch
    test_samples, test_stats = _collect_or_load(
        test_rows, out / "signals_test.json", test_cache, args.concurrency, log, "test", progress
    )
    val_samples, val_stats = _collect_or_load(
        val_rows, out / "signals_validation.json", val_cache, args.concurrency, log, "validation", progress
    )
    meta["reliability"] = {
        "test": test_stats.to_dict() if test_stats else "loaded_from_cache",
        "validation": val_stats.to_dict() if val_stats else "loaded_from_cache",
    }

    # Integrity guard: never publish metrics computed on a mostly-failed run.
    if test_stats is not None and test_stats.success_rate < args.min_success_rate:
        (out / "REPORT.md").write_text(
            "# Benchmark ABORTED\n\n"
            f"Only {test_stats.scored_ok}/{test_stats.requested} test extractions "
            f"succeeded (success rate {test_stats.success_rate:.1%}), below the "
            f"--min-success-rate {args.min_success_rate:.0%} threshold. No metrics "
            "were computed to avoid reporting results from an unreliable run.\n\n"
            f"Reliability: {test_stats.to_dict()}\n",
            encoding="utf-8",
        )
        (out / "report.json").write_text(
            json.dumps({"status": "aborted", "meta": meta}, indent=2), encoding="utf-8"
        )
        log.event("abort", reason="success_rate_below_threshold", **test_stats.to_dict())
        log.close()
        raise SystemExit(
            f"ABORTED: test success rate {test_stats.success_rate:.1%} < "
            f"{args.min_success_rate:.0%}. Check the DeepSeek key / proxy. See {out}."
        )
    if len(test_samples) < 2:
        log.event("abort", reason="too few valid test samples")
        log.close()
        raise SystemExit("Too few valid samples scored — check the DeepSeek key / proxy.")

    # --- 3. evaluate with default weights --------------------------------
    default_params = load_params()
    preds_d, truths = score_with_params(test_samples, default_params)
    report_default = compute_report_with_ci(preds_d, truths, n_boot=args.n_boot)
    log.event("eval_default", **report_default.to_dict())

    # --- 4. tune on validation -------------------------------------------
    best_params, best_val_r = _tune(val_samples, args.trials, log)

    # persist tuned params where config.load_params() will pick them up
    import epistemic_math

    tuned_dict = {
        "alpha": best_params.alpha,
        "beta": best_params.beta,
        "gamma": best_params.gamma,
        "lambda_": best_params.lambda_,
        "prior_strength": best_params.prior_strength,
        "pearson_r_validation": best_val_r,
    }
    (out / "tuned_params.json").write_text(json.dumps(tuned_dict, indent=2), encoding="utf-8")
    Path(epistemic_math.__file__).with_name("tuned_params.json").write_text(
        json.dumps(tuned_dict, indent=2), encoding="utf-8"
    )

    # --- 5. re-evaluate on test with tuned weights -----------------------
    preds_t, _ = score_with_params(test_samples, best_params)
    report_tuned = compute_report_with_ci(preds_t, truths, n_boot=args.n_boot)
    log.event("eval_tuned", **report_tuned.to_dict())

    # --- 6. persist predictions + reports --------------------------------
    preds_neutral, _ = score_with_params(test_samples, default_params, neutral_prior=True)
    _write_predictions(out / "predictions.csv", test_samples, preds_neutral, preds_d, preds_t)

    report = {
        "meta": meta,
        "results": {
            "default_weights": {**asdict(default_params), **report_default.to_dict()},
            "tuned_weights": {**asdict(best_params), **report_tuned.to_dict()},
            "tuning_validation_pearson": best_val_r,
        },
    }
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out / "REPORT.md").write_text(_markdown_report(report), encoding="utf-8")

    log.event("benchmark_complete", out_dir=str(out))
    log.close()

    print(f"\n=== Benchmark complete → {out} ===")
    print(_markdown_report(report))


def _write_predictions(path: Path, samples, preds_neutral, preds_credibility, preds_tuned) -> None:  # noqa: ANN001
    """Per-statement export: EIS under each ablation condition vs ground truth.

    Columns: eis_neutral (A, content-only), eis_credibility (B, + speaker prior,
    default weights), eis_tuned (C, + tuned weights).
    """
    scored = [s for s in samples if s.claims]
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["idx", "label", "truth_score", "eis_neutral", "eis_credibility", "eis_tuned", "statement"]
        )
        for i, (s, pa, pb, pt) in enumerate(zip(scored, preds_neutral, preds_credibility, preds_tuned)):
            w.writerow(
                [i, s.label, round(s.truth_score, 3), round(pa, 4), round(pb, 4), round(pt, 4), s.statement]
            )


def _fmt_ci(ci) -> str:  # noqa: ANN001
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci else "n/a"


def _markdown_report(report: dict) -> str:
    m = report["meta"]
    d = report["results"]["default_weights"]
    t = report["results"]["tuned_weights"]
    ds = m["dataset"]
    lines = [
        "# Epis-KG — Empirical Evaluation Report",
        "",
        f"*Generated {m['timestamp']} UTC · commit `{m['git_commit'][:10]}` · "
        f"model `{m['llm_model']}` via `{m['llm_provider']}`*",
        "",
        "## 1. Dataset",
        "",
        f"Benchmark: **LIAR** (Wang, 2017). Test n = **{ds['test']['n']}**, "
        f"validation n = **{ds['validation']['n']}**. Six-point veracity labels "
        "mapped to a continuous [0,1] scale (pants-fire=0.0 … true=1.0).",
        "",
        f"Test label distribution: `{ds['test']['labels']}`",
        "",
        "## 1b. Pipeline reliability",
        "",
        "Metrics are computed **only on schema-valid extractions**. LLM "
        "connection/parse failures and extractions that failed validation after "
        "all self-correction attempts are excluded and reported here — no row is "
        "ever assigned a fabricated score.",
        "",
        f"- Test: `{m.get('reliability', {}).get('test')}`",
        f"- Validation: `{m.get('reliability', {}).get('validation')}`",
        "",
        "## 2. Method",
        "",
        "Each statement is decomposed by the multi-agent LangGraph pipeline into "
        "atomic claims + rhetoric; the Epistemic Integrity Score (EIS) is computed "
        "by the `epistemic_math` engine. We report the correlation of the EIS with "
        "ground-truth veracity and the AUC-ROC of the EIS as a truthfulness "
        "classifier (true-ish = veracity ≥ 0.5). 95% CIs are bootstrap "
        f"({m['config']['n_boot']} resamples).",
        "",
        "## 3. Results (held-out test split)",
        "",
        "| Configuration | Pearson r (95% CI) | Spearman ρ | AUC-ROC (95% CI) | n |",
        "|---|---|---|---|---|",
        f"| Default weights | {d['pearson_r']:.3f} {_fmt_ci(d.get('pearson_ci95'))} | "
        f"{d['spearman_r']:.3f} | {d['auc_roc']:.3f} {_fmt_ci(d.get('auc_ci95'))} | {d['n']} |",
        f"| **Optuna-tuned** | {t['pearson_r']:.3f} {_fmt_ci(t.get('pearson_ci95'))} | "
        f"{t['spearman_r']:.3f} | {t['auc_roc']:.3f} {_fmt_ci(t.get('auc_ci95'))} | {t['n']} |",
        "",
        "## 4. Tuned hyperparameters",
        "",
        f"Selected on the validation split (best Pearson r = "
        f"{report['results']['tuning_validation_pearson']:.3f}):",
        "",
        f"- α (rhetoric) = **{t['alpha']:.3f}**",
        f"- β (contradiction) = **{t['beta']:.3f}**",
        f"- γ (temporal) = **{t['gamma']:.3f}**",
        f"- λ (decay const) = **{t['lambda_']:.3f}**",
        f"- prior strength = **{t['prior_strength']:.3f}**",
        "",
        "## 5. Reproducibility & artifacts",
        "",
        "This report ships with: `signals_{test,validation}.json` (cached "
        "per-claim signals), `predictions.csv` (per-statement EIS vs truth), "
        "`tuned_params.json`, `report.json`, and `run.log` (JSON-lines trace). "
        f"Package versions: `{m['packages']}`.",
        "",
        "## 6. Notes & limitations",
        "",
        "- LIAR labels rate *claim veracity*; the EIS measures *epistemic "
        "integrity* (evidence, rhetoric, contradiction, decay). Correlation is "
        "expected but the constructs are not identical — the EIS additionally "
        "penalises manipulative-but-true and rewards well-sourced framing.",
        "- Extraction is LLM-based; consensus mode (two models) can be enabled to "
        "further reduce extraction variance.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
