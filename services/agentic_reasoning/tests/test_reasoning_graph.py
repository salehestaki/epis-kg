"""Deterministic tests for the reasoning graph using a scripted LLM client."""

from __future__ import annotations

import pytest

from agentic_reasoning.llm_client import JSONChatClient
from agentic_reasoning.state import ReasoningState
from agentic_reasoning.workflows.graph import build_reasoning_graph
from graph_schema import RawDocument


class ScriptedClient(JSONChatClient):
    """Returns queued responses keyed by a marker in the system prompt."""

    def __init__(self, responses: dict[str, list]) -> None:  # noqa: D401
        self._responses = {k: list(v) for k, v in responses.items()}

    async def complete_json(self, system: str, user: str):  # type: ignore[override]
        if "ExtractorAgent" in system:
            key = "extract"
        elif "RhetoricAgent" in system:
            key = "rhetoric"
        else:
            key = "contradiction"
        queue = self._responses.get(key)
        if not queue:
            return {} if key != "contradiction" else {"contradictions": []}
        return queue.pop(0)


def _doc() -> RawDocument:
    return RawDocument(id="d1", content="The water is toxic. Officials say it is safe.",
                       source_name="Tester", a_priori_credibility=0.5)


@pytest.mark.asyncio
async def test_happy_path_produces_valid_result():
    client = ScriptedClient(
        {
            "extract": [
                {
                    "claims": [
                        {"id": "c1", "statement": "The water is toxic", "confidence": 0.8},
                        {"id": "c2", "statement": "The water is safe", "confidence": 0.7},
                    ],
                    "evidence": [{"id": "e1", "type": "citation"}],
                    "supported_by": {"c2": ["e1"]},
                    "decontextualizes": {},
                }
            ],
            "rhetoric": [
                {
                    "rhetoric": [
                        {"id": "r1", "category": "Appeal to Fear", "severity_weight": 0.7}
                    ],
                    "employs_rhetoric": ["r1"],
                }
            ],
            "contradiction": [
                {"contradictions": [{"source_claim_id": "c1", "target_claim_id": "c2"}]}
            ],
        }
    )
    graph = build_reasoning_graph(client)
    state: ReasoningState = {"document": _doc(), "attempts": 0, "errors": []}
    final = await graph.ainvoke(state)

    assert final["valid"] is True
    result = final["result"]
    assert {c.id for c in result.claims} == {"c1", "c2"}
    assert result.rhetoric[0].category.value == "Appeal to Fear"
    assert result.contradictions[0].target_claim_id == "c2"
    assert final["attempts"] == 1


@pytest.mark.asyncio
async def test_self_correction_loop_recovers_from_bad_category():
    client = ScriptedClient(
        {
            "extract": [
                # attempt 1 - fine
                {"claims": [{"id": "c1", "statement": "X", "confidence": 0.5}],
                 "evidence": [], "supported_by": {}, "decontextualizes": {}},
                # attempt 2 - fine again (after retry)
                {"claims": [{"id": "c1", "statement": "X", "confidence": 0.5}],
                 "evidence": [], "supported_by": {}, "decontextualizes": {}},
            ],
            "rhetoric": [
                # attempt 1 - INVALID category -> forces a retry
                {"rhetoric": [{"id": "r1", "category": "Totally Made Up"}],
                 "employs_rhetoric": ["r1"]},
                # attempt 2 - valid category
                {"rhetoric": [{"id": "r1", "category": "Loaded Language"}],
                 "employs_rhetoric": ["r1"]},
            ],
            "contradiction": [{"contradictions": []}, {"contradictions": []}],
        }
    )
    graph = build_reasoning_graph(client)
    state: ReasoningState = {"document": _doc(), "attempts": 0, "errors": []}
    final = await graph.ainvoke(state)

    assert final["valid"] is True
    assert final["attempts"] == 2  # looped once
    assert final["result"].rhetoric[0].category.value == "Loaded Language"
