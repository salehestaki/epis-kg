"""Generate publication-ready (IEEE-style) figures from a benchmark artifact.

Reads the cached signals of the final benchmark run, recomputes the per-statement
Epistemic Integrity Score under the ablation conditions, (re)writes an enriched
predictions.csv, and renders two figures to docs/figures/ as vector PDF + 300-DPI
PNG:

  fig_roc      — ROC curves, Condition A (content-only) vs B (+ credibility prior)
  fig_eis_dist — violin/box distribution of the EIS across the six LIAR labels

Usage:
    python scripts/generate_plots.py                 # latest benchmark_* dir
    python scripts/generate_plots.py <benchmark_dir>
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for pkg in ("graph_schema", "epistemic_math", "observability", "evaluation"):
    sys.path.insert(0, str(ROOT / "packages" / pkg))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.metrics import auc, roc_curve  # noqa: E402

from epistemic_math import load_params  # noqa: E402
from evaluation.liar import load_liar  # noqa: E402
from evaluation.pipeline import score_with_params  # noqa: E402
from evaluation.signals_io import load_signals  # noqa: E402

LABEL_ORDER = ["pants-fire", "false", "barely-true", "half-true", "mostly-true", "true"]
LABEL_SHORT = ["pants\nfire", "false", "barely\ntrue", "half\ntrue", "mostly\ntrue", "true"]
# Okabe-Ito colourblind-safe palette
C_A, C_B, C_ACCENT = "#E69F00", "#0072B2", "#009E73"


def _ieee_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "mathtext.fontset": "stix",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "figure.dpi": 300,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "axes.grid": True,
            "grid.alpha": 0.3,
            "grid.linewidth": 0.5,
            "axes.axisbelow": True,
        }
    )


def _save(fig, outdir: Path, name: str) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    fig.savefig(outdir / f"{name}.pdf")
    fig.savefig(outdir / f"{name}.png")
    plt.close(fig)
    print(f"  wrote {outdir / name}.pdf / .png")


def main() -> None:
    _ieee_style()
    if len(sys.argv) > 1:
        bench = Path(sys.argv[1])
    else:
        dirs = sorted((ROOT / "artifacts").glob("benchmark_*"), reverse=True)
        if not dirs:
            raise SystemExit("no benchmark_* artifact found under artifacts/")
        bench = dirs[0]
    print(f"Benchmark: {bench}")

    samples = load_signals(bench / "signals_test.json")
    priors = {r["statement"]: r["prior_credibility"] for r in load_liar(split="test")}
    params = load_params()

    eis_a, truths = score_with_params(samples, params, neutral_prior=True)
    eis_b, _ = score_with_params(samples, params, priors=priors)
    scored = [s for s in samples if s.claims]
    labels = [s.label for s in scored]
    eis_a, eis_b, truths = np.array(eis_a), np.array(eis_b), np.array(truths)
    y_true = (truths >= 0.5).astype(int)
    print(f"n = {len(scored)}  |  positives = {int(y_true.sum())}")

    # (re)write an enriched predictions.csv aligned with the ablation columns
    with (bench / "predictions.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["idx", "label", "truth_score", "eis_neutral", "eis_credibility", "statement"])
        for i, s in enumerate(scored):
            w.writerow([i, s.label, round(s.truth_score, 3), round(float(eis_a[i]), 4),
                        round(float(eis_b[i]), 4), s.statement])

    figdir = ROOT / "docs" / "figures"
    _plot_roc(y_true, eis_a, eis_b, figdir)
    _plot_distribution(labels, eis_b, figdir)
    print("Done.")


def _plot_roc(y_true, eis_a, eis_b, outdir: Path) -> None:  # noqa: ANN001
    fig, ax = plt.subplots(figsize=(3.4, 3.1))
    for eis, colour, name in ((eis_a, C_A, "A: content-only"), (eis_b, C_B, "B: + credibility prior")):
        fpr, tpr, _ = roc_curve(y_true, eis)
        a = auc(fpr, tpr)
        ax.plot(fpr, tpr, color=colour, lw=1.8, label=f"{name} (AUC = {a:.3f})")
    ax.plot([0, 1], [0, 1], color="0.6", lw=0.9, ls="--", label="chance")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC — truthfulness discrimination")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(loc="lower right", frameon=False)
    _save(fig, outdir, "fig_roc")


def _plot_distribution(labels, eis_b, outdir: Path) -> None:  # noqa: ANN001
    data = [np.array([eis_b[i] for i, lb in enumerate(labels) if lb == lab]) for lab in LABEL_ORDER]
    data = [d if d.size else np.array([np.nan]) for d in data]
    pos = np.arange(1, len(LABEL_ORDER) + 1)

    fig, ax = plt.subplots(figsize=(3.6, 2.9))
    parts = ax.violinplot(data, positions=pos, showextrema=False, widths=0.85)
    # Colour-graded from red (false) to green (true)
    cmap = plt.cm.RdYlGn
    for i, body in enumerate(parts["bodies"]):
        body.set_facecolor(cmap(i / (len(LABEL_ORDER) - 1)))
        body.set_edgecolor("0.3")
        body.set_alpha(0.75)
    ax.boxplot(data, positions=pos, widths=0.18, showfliers=False,
               medianprops=dict(color="black", lw=1.1),
               boxprops=dict(color="0.25", lw=0.8),
               whiskerprops=dict(color="0.25", lw=0.8), capprops=dict(color="0.25", lw=0.8))
    means = [np.nanmean(d) for d in data]
    ax.plot(pos, means, color=C_B, marker="o", ms=3.5, lw=1.2, label="mean EIS")
    ax.set_xticks(pos)
    ax.set_xticklabels(LABEL_SHORT)
    ax.set_ylabel("Epistemic Integrity Score")
    ax.set_xlabel("LIAR ground-truth label (deceptive → truthful)")
    ax.set_title("EIS distribution across veracity labels")
    ax.set_ylim(0, 1)
    ax.legend(loc="upper left", frameon=False)
    _save(fig, outdir, "fig_eis_dist")


if __name__ == "__main__":
    main()
