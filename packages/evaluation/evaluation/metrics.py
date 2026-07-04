"""Correlation and classification metrics for EIS vs ground truth."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class EvalReport:
    n: int
    pearson_r: float
    pearson_p: float
    spearman_r: float
    auc_roc: float
    threshold: float
    pearson_ci95: tuple[float, float] | None = None
    auc_ci95: tuple[float, float] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def compute_report(
    preds: list[float], truths: list[float], veracity_threshold: float = 0.5
) -> EvalReport:
    """Pearson + Spearman correlation and binary AUC-ROC.

    ``preds`` are Epistemic Integrity Scores in [0,1]; ``truths`` are LIAR
    veracity scores in [0,1]. For AUC we binarise truth as "true-ish"
    (score >= threshold) and use the EIS directly as the score.
    """
    import numpy as np
    from scipy.stats import pearsonr, spearmanr
    from sklearn.metrics import roc_auc_score

    p = np.asarray(preds, dtype=float)
    t = np.asarray(truths, dtype=float)
    if len(p) < 2:
        raise ValueError("need at least 2 samples")

    pr, pp = pearsonr(p, t)
    sr, _ = spearmanr(p, t)

    y_true = (t >= veracity_threshold).astype(int)
    if y_true.min() == y_true.max():
        auc = float("nan")  # only one class present
    else:
        auc = float(roc_auc_score(y_true, p))

    return EvalReport(
        n=len(p),
        pearson_r=float(pr),
        pearson_p=float(pp),
        spearman_r=float(sr),
        auc_roc=auc,
        threshold=veracity_threshold,
    )


def compute_report_with_ci(
    preds: list[float],
    truths: list[float],
    veracity_threshold: float = 0.5,
    n_boot: int = 1000,
    seed: int = 42,
) -> EvalReport:
    """Point estimates plus 95% bootstrap confidence intervals (Q1 rigour)."""
    import numpy as np
    from scipy.stats import pearsonr
    from sklearn.metrics import roc_auc_score

    report = compute_report(preds, truths, veracity_threshold)
    p = np.asarray(preds, dtype=float)
    t = np.asarray(truths, dtype=float)
    y = (t >= veracity_threshold).astype(int)
    rng = np.random.default_rng(seed)
    n = len(p)

    pear_samples: list[float] = []
    auc_samples: list[float] = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        pb, tb, yb = p[idx], t[idx], y[idx]
        if len(set(tb.tolist())) > 1 and len(set(pb.tolist())) > 1:
            pear_samples.append(float(pearsonr(pb, tb)[0]))
        if yb.min() != yb.max():
            auc_samples.append(float(roc_auc_score(yb, pb)))

    def _ci(vals: list[float]) -> tuple[float, float] | None:
        if len(vals) < 20:
            return None
        lo, hi = np.percentile(vals, [2.5, 97.5])
        return (round(float(lo), 4), round(float(hi), 4))

    report.pearson_ci95 = _ci(pear_samples)
    report.auc_ci95 = _ci(auc_samples)
    return report
