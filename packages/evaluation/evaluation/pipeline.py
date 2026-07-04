"""Run statements through the reasoning pipeline and cache decay *signals*.

Running the LLM extraction is the expensive part, so we do it **once** and cache
the per-claim signals. Both the evaluation and the Optuna tuner then recompute
the Epistemic Integrity Score cheaply for any hyperparameter set without hitting
the LLM again.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from epistemic_math import ClaimSignals, EpistemicParams, RhetoricSignal, epistemic_integrity_score
from graph_schema import ExtractionResult, RawDocument
from observability import get_logger

_log = get_logger("evaluation.pipeline")

# Neutral prior for LIAR: the dataset has no per-source credibility we trust.
_NEUTRAL_CREDIBILITY = 0.5


@dataclass
class ClaimBlueprint:
    """Everything needed to (re)compute one claim's EIS, minus the params."""

    a_priori_credibility: float
    n_support: int
    contradictions_in_degree: int
    total_degree: int
    age_days: float
    rhetoric: list[tuple[float, bool]]  # (severity_weight, is_active_vulnerability)

    def to_signals(self) -> ClaimSignals:
        return ClaimSignals(
            a_priori_credibility=self.a_priori_credibility,
            n_support=self.n_support,
            contradictions_in_degree=self.contradictions_in_degree,
            total_degree=self.total_degree,
            age_days=self.age_days,
            rhetoric=[RhetoricSignal(s, a) for (s, a) in self.rhetoric],
        )


@dataclass
class ScoredSample:
    truth_score: float
    claims: list[ClaimBlueprint] = field(default_factory=list)
    statement: str = ""
    label: str = ""


def _blueprints_from_result(
    result: ExtractionResult, prior: float = _NEUTRAL_CREDIBILITY
) -> list[ClaimBlueprint]:
    rhetoric = [(r.severity_weight or 0.5, r.is_active_vulnerability) for r in result.rhetoric]
    contra_in: dict[str, int] = {c.id: 0 for c in result.claims}
    contra_out: dict[str, int] = {c.id: 0 for c in result.claims}
    for con in result.contradictions:
        if con.target_claim_id in contra_in:
            contra_in[con.target_claim_id] += 1
        if con.source_claim_id in contra_out:
            contra_out[con.source_claim_id] += 1

    blueprints: list[ClaimBlueprint] = []
    for c in result.claims:
        n_support = len(result.supported_by.get(c.id, []))
        total_degree = 1 + n_support + contra_in[c.id] + contra_out[c.id]  # 1 = CONTAINS
        blueprints.append(
            ClaimBlueprint(
                a_priori_credibility=prior,
                n_support=n_support,
                contradictions_in_degree=contra_in[c.id],
                total_degree=total_degree,
                age_days=0.0,
                rhetoric=rhetoric,
            )
        )
    return blueprints


@dataclass
class PipelineStats:
    """Reliability accounting so reported results are honest, never fabricated.

    A row is only counted ``ok`` (and scored) when the pipeline returned a
    schema-VALID extraction. LLM connection/parse errors and extractions that
    failed validation after all retries are recorded and *excluded* — they never
    contribute a made-up score.
    """

    requested: int = 0
    scored_ok: int = 0
    invalid: int = 0
    errors: int = 0

    @property
    def failed(self) -> int:
        return self.invalid + self.errors

    @property
    def success_rate(self) -> float:
        return self.scored_ok / self.requested if self.requested else 0.0

    def to_dict(self) -> dict:
        return {
            "requested": self.requested,
            "scored_ok": self.scored_ok,
            "invalid": self.invalid,
            "errors": self.errors,
            "failed": self.failed,
            "success_rate": round(self.success_rate, 4),
        }


async def _run_one(  # noqa: ANN001
    graph, statement: str, idx: int, prior: float = _NEUTRAL_CREDIBILITY
) -> tuple[list[ClaimBlueprint], str]:
    """Return ``(blueprints, status)`` where status is ok | invalid | error.

    * ``error``   — the LLM could not be reached / returned unparsable output
                    even after retries (nothing is scored for this row).
    * ``invalid`` — the model responded but the extraction failed the ontology
                    schema after all self-correction attempts (excluded).
    * ``ok``      — a schema-valid extraction with >= 1 atomic claim.
    """
    doc = RawDocument(id=f"liar_{idx}", content=statement, source_name="LIAR")
    try:
        final = await graph.ainvoke({"document": doc, "attempts": 0, "errors": []})
    except Exception as exc:  # noqa: BLE001 - connection/timeout/parse failure
        _log.warning("pipeline_row_error", idx=idx, error=str(exc))
        return [], "error"
    if not final.get("valid"):
        _log.warning("pipeline_row_invalid", idx=idx, errors=(final.get("errors") or [])[-2:])
        return [], "invalid"
    result = final.get("result")
    if result is None or not result.claims:
        return [], "invalid"
    return _blueprints_from_result(result, prior), "ok"


async def collect_signals_async(
    rows: list[dict],
    concurrency: int = 4,
    cache=None,  # noqa: ANN001 - StatementCache
    progress_path=None,  # noqa: ANN001 - Path | None
    label: str = "",
) -> tuple[list[ScoredSample], PipelineStats]:
    """Run every row through the reasoning graph. Returns (scored samples, stats).

    Only schema-valid extractions are returned; failures are counted in stats
    and dropped, so downstream metrics are computed exclusively on real,
    validated data. An optional persistent ``cache`` (StatementCache) makes long
    runs resumable — already-extracted statements are reused, never re-called.

    When ``progress_path`` is given, a live JSON progress file (percent, rate,
    ETA, ok/failed counts) is flushed to disk so operators can watch a long run
    and tell whether it is advancing or stuck. Needs LLM credentials.
    """
    from agentic_reasoning import build_reasoning_graph

    graph = build_reasoning_graph()
    sem = asyncio.Semaphore(concurrency)
    samples: list[ScoredSample] = [
        ScoredSample(truth_score=r["score"], statement=r["statement"], label=r.get("label", ""))
        for r in rows
    ]
    total = len(rows)
    statuses: list[str] = ["error"] * total
    done = 0
    ok = 0
    failed = 0
    start = time.monotonic()

    def _write_progress(force: bool = False) -> None:
        if progress_path is None:
            return
        if not force and done % 5 != 0:
            return
        elapsed = time.monotonic() - start
        rate = done / elapsed if elapsed > 0 else 0.0
        remaining = total - done
        eta_s = remaining / rate if rate > 0 else None
        payload = {
            "split": label,
            "done": done,
            "total": total,
            "percent": round(100.0 * done / total, 1) if total else 100.0,
            "ok": ok,
            "failed": failed,
            "elapsed_min": round(elapsed / 60, 1),
            "rate_per_min": round(rate * 60, 2),
            "eta_min": round(eta_s / 60, 1) if eta_s is not None else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = Path(str(progress_path) + ".tmp")
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(progress_path)

    async def _worker(i: int, row: dict) -> None:
        nonlocal done, ok, failed
        statement = row["statement"]
        if cache is not None:
            hit = cache.get(statement)
            if hit is not None:
                samples[i].claims = hit
                statuses[i] = "cached"
                done += 1
                ok += 1
                _write_progress()
                return
        async with sem:
            prior = float(row.get("prior_credibility", _NEUTRAL_CREDIBILITY))
            blueprints, status = await _run_one(graph, statement, i, prior)
            samples[i].claims = blueprints
            statuses[i] = status
            if status == "ok" and cache is not None:
                cache.put(statement, blueprints)
            done += 1
            if status in ("ok", "cached"):
                ok += 1
            else:
                failed += 1
            if done % 10 == 0:
                _log.info(
                    "pipeline_progress",
                    split=label,
                    done=done,
                    total=total,
                    percent=round(100.0 * done / total, 1),
                    ok=ok,
                    failed=failed,
                )
            _write_progress()

    await asyncio.gather(*(_worker(i, r) for i, r in enumerate(rows)))
    _write_progress(force=True)

    # --- retry pass: transient errors (timeouts) get one more try, rotating to
    # another API key. Persistent schema-invalids are left as-is.
    retry_idx = [i for i, st in enumerate(statuses) if st == "error"]
    if retry_idx and os.getenv("EPIS_RETRY_ERRORS", "true").lower() in ("1", "true", "yes"):
        _log.info("retry_pass_start", count=len(retry_idx), split=label)

        async def _retry(i: int) -> None:
            nonlocal ok, failed
            async with sem:
                row = rows[i]
                prior = float(row.get("prior_credibility", _NEUTRAL_CREDIBILITY))
                blueprints, status = await _run_one(graph, row["statement"], i, prior)
                if status == "ok":
                    samples[i].claims = blueprints
                    statuses[i] = "ok"
                    ok += 1
                    failed -= 1
                    if cache is not None:
                        cache.put(row["statement"], blueprints)
                _write_progress()

        await asyncio.gather(*(_retry(i) for i in retry_idx))
        recovered = sum(1 for i in retry_idx if statuses[i] == "ok")
        _log.info("retry_pass_done", recovered=recovered, of=len(retry_idx), split=label)
        _write_progress(force=True)

    stats = PipelineStats(requested=len(rows))
    for st in statuses:
        if st in ("ok", "cached"):
            stats.scored_ok += 1
        elif st == "invalid":
            stats.invalid += 1
        else:
            stats.errors += 1
    _log.info("pipeline_reliability", **stats.to_dict())
    return [s for s in samples if s.claims], stats


def collect_signals_with_stats(
    rows: list[dict],
    concurrency: int = 4,
    cache=None,  # noqa: ANN001
    progress_path=None,  # noqa: ANN001
    label: str = "",
) -> tuple[list[ScoredSample], PipelineStats]:
    return asyncio.run(
        collect_signals_async(rows, concurrency, cache, progress_path, label)
    )


def collect_signals(rows: list[dict], concurrency: int = 4) -> list[ScoredSample]:
    return asyncio.run(collect_signals_async(rows, concurrency))[0]


def score_with_params(
    samples: list[ScoredSample],
    params: EpistemicParams,
    priors: dict[str, float] | None = None,
    neutral_prior: bool = False,
) -> tuple[list[float], list[float]]:
    """Return ``(predicted_eis, truth_scores)`` for the given hyperparameters.

    A statement's predicted integrity is the mean EIS of its atomic claims.
    Cheap: no LLM calls, so it can run inside an Optuna objective thousands of
    times, or drive a prior-ablation.

    Parameters
    ----------
    priors:
        Optional ``{statement: prior_credibility}`` overriding the Bayesian prior
        anchor per sample (e.g. LIAR speaker credit-history). Enables the
        credibility-prior condition without re-running extraction.
    neutral_prior:
        Force a 0.5 neutral prior for every claim (content-only ablation).
    """
    preds: list[float] = []
    truths: list[float] = []
    for s in samples:
        if not s.claims:
            continue
        override: float | None = None
        if neutral_prior:
            override = 0.5
        elif priors is not None:
            override = priors.get(s.statement)
        eis_vals: list[float] = []
        for c in s.claims:
            sig = c.to_signals()
            if override is not None:
                sig.a_priori_credibility = override
            eis_vals.append(epistemic_integrity_score(sig, params))
        preds.append(sum(eis_vals) / len(eis_vals))
        truths.append(s.truth_score)
    return preds, truths
