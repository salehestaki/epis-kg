"""Benchmark the Epistemic Integrity Score against the LIAR dataset.

Usage:
    python -m evaluation.evaluate_eis --split test --limit 500

Downloads LIAR automatically, runs each statement through the Epis-KG reasoning
pipeline, computes the EIS, and reports Pearson/Spearman correlation and
AUC-ROC against the ground-truth veracity labels. Requires LLM API keys
(LLM_PROVIDER + key) because it exercises the real extraction pipeline.
"""

from __future__ import annotations

import argparse
import json

from evaluation.env import load_dotenv
from evaluation.liar import load_liar
from evaluation.metrics import compute_report
from evaluation.pipeline import collect_signals, score_with_params
from epistemic_math import load_params
from observability import configure_logging, get_logger

_log = get_logger("evaluation.evaluate_eis")


def main() -> None:
    load_dotenv()
    configure_logging()
    ap = argparse.ArgumentParser(description="Evaluate Epis-KG EIS vs LIAR")
    ap.add_argument("--split", default="test", choices=["train", "validation", "test"])
    ap.add_argument("--limit", type=int, default=200, help="max statements (cost control)")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--out", default="eval_report.json")
    args = ap.parse_args()

    rows = load_liar(split=args.split, limit=args.limit)
    _log.info("running_pipeline", rows=len(rows))
    samples = collect_signals(rows, concurrency=args.concurrency)
    if not samples:
        raise SystemExit("no samples scored — check LLM credentials / connectivity")

    preds, truths = score_with_params(samples, load_params())
    report = compute_report(preds, truths)

    payload = {"split": args.split, "requested": args.limit, **report.to_dict()}
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)

    print(json.dumps(payload, indent=2))
    _log.info("evaluation_complete", **report.to_dict())


if __name__ == "__main__":
    main()
