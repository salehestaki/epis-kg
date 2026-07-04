"""Tests for honest failure accounting (no fabricated scores on LLM errors)."""

import pytest

from evaluation.pipeline import PipelineStats, _run_one
from graph_schema import Claim, Document, ExtractionResult, Source


def _valid_result() -> ExtractionResult:
    return ExtractionResult(
        document=Document(id="d", content="x"),
        source=Source(id="s", name="LIAR"),
        claims=[Claim(id="c1", statement="A")],
        contains=["c1"],
    )


class _Graph:
    def __init__(self, behaviour: str) -> None:
        self._behaviour = behaviour

    async def ainvoke(self, state):  # noqa: ANN001
        if self._behaviour == "raise":
            raise RuntimeError("connection refused")
        if self._behaviour == "ok":
            return {"valid": True, "result": _valid_result()}
        if self._behaviour == "invalid":
            return {"valid": False, "errors": ["bad category"], "result": _valid_result()}
        return {"valid": True, "result": None}  # empty


def test_pipeline_stats_math():
    s = PipelineStats(requested=10, scored_ok=7, invalid=2, errors=1)
    assert s.failed == 3
    assert s.success_rate == 0.7


@pytest.mark.asyncio
async def test_run_one_error_is_not_scored():
    bp, status = await _run_one(_Graph("raise"), "stmt", 0)
    assert status == "error"
    assert bp == []  # no fabricated signal


@pytest.mark.asyncio
async def test_run_one_invalid_is_excluded():
    bp, status = await _run_one(_Graph("invalid"), "stmt", 0)
    assert status == "invalid"
    assert bp == []


@pytest.mark.asyncio
async def test_run_one_ok_is_scored():
    bp, status = await _run_one(_Graph("ok"), "stmt", 0)
    assert status == "ok"
    assert len(bp) == 1


@pytest.mark.asyncio
async def test_run_one_empty_result_is_invalid():
    bp, status = await _run_one(_Graph("empty"), "stmt", 0)
    assert status == "invalid"
    assert bp == []
