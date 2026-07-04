"""Persistent per-statement extraction cache (resumable long runs).

A full LIAR run is ~1.3k LLM extractions over a couple of hours; a transient
proxy hiccup shouldn't force starting over. This cache stores each statement's
extracted signals as a JSON line keyed by the statement, so a re-run skips work
already done. Only successful (``ok``) extractions are cached — failures are
retried on the next run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from evaluation.pipeline import ClaimBlueprint


def _key(statement: str) -> str:
    return hashlib.sha1(statement.encode("utf-8")).hexdigest()  # noqa: S324 - not security


class StatementCache:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._mem: dict[str, list[ClaimBlueprint]] = {}
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._mem[row["key"]] = [
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

    def get(self, statement: str) -> list[ClaimBlueprint] | None:
        return self._mem.get(_key(statement))

    def put(self, statement: str, blueprints: list[ClaimBlueprint]) -> None:
        key = _key(statement)
        self._mem[key] = blueprints
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "key": key,
            "claims": [
                {
                    "a_priori_credibility": c.a_priori_credibility,
                    "n_support": c.n_support,
                    "contradictions_in_degree": c.contradictions_in_degree,
                    "total_degree": c.total_degree,
                    "age_days": c.age_days,
                    "rhetoric": [[sev, act] for (sev, act) in c.rhetoric],
                }
                for c in blueprints
            ],
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def __len__(self) -> int:
        return len(self._mem)
