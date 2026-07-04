"""Persist and reload cached pipeline signals.

Running the LLM pipeline is the costly step. Saving the extracted per-claim
signals to disk makes the whole benchmark reproducible and lets the evaluator
and the Optuna tuner reuse one extraction pass — no duplicate API spend, and the
cached signals are themselves a publishable artifact.
"""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.pipeline import ClaimBlueprint, ScoredSample


def save_signals(samples: list[ScoredSample], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "truth_score": s.truth_score,
            "statement": s.statement,
            "label": s.label,
            "claims": [
                {
                    "a_priori_credibility": c.a_priori_credibility,
                    "n_support": c.n_support,
                    "contradictions_in_degree": c.contradictions_in_degree,
                    "total_degree": c.total_degree,
                    "age_days": c.age_days,
                    "rhetoric": [[sev, act] for (sev, act) in c.rhetoric],
                }
                for c in s.claims
            ],
        }
        for s in samples
    ]
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def load_signals(path: str | Path) -> list[ScoredSample]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    samples: list[ScoredSample] = []
    for row in data:
        claims = [
            ClaimBlueprint(
                a_priori_credibility=c["a_priori_credibility"],
                n_support=c["n_support"],
                contradictions_in_degree=c["contradictions_in_degree"],
                total_degree=c["total_degree"],
                age_days=c["age_days"],
                rhetoric=[(sev, bool(act)) for sev, act in c["rhetoric"]],
            )
            for c in row["claims"]
        ]
        samples.append(
            ScoredSample(
                truth_score=row["truth_score"],
                statement=row.get("statement", ""),
                label=row.get("label", ""),
                claims=claims,
            )
        )
    return samples
