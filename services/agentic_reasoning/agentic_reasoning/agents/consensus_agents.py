"""Consensus variants of the extraction / rhetoric agents.

Each runs two independent LLMs concurrently and keeps only the items both models
agree on, then filters the dependent edges (supported_by / decontextualizes /
employs_rhetoric) down to the surviving nodes.
"""

from __future__ import annotations

import asyncio
import os

from agentic_reasoning.consensus import agree_claims, agree_rhetoric
from agentic_reasoning.llm_client import ChatSettings, JSONChatClient
from agentic_reasoning.prompts import (
    EXTRACTOR_SYSTEM,
    RHETORIC_SYSTEM,
    extractor_user,
    rhetoric_user,
)
from agentic_reasoning.state import ReasoningState
from observability import get_logger, traced

_log = get_logger("reasoning.consensus")


def _second_client() -> JSONChatClient:
    """The second opinion. Defaults to OpenAI gpt-4o-mini."""
    return JSONChatClient(
        ChatSettings(
            provider=os.getenv("EPIS_CONSENSUS_PROVIDER_B", "openai"),
            model=os.getenv("EPIS_CONSENSUS_MODEL_B", "gpt-4o-mini"),
        )
    )


class ConsensusExtractorAgent:
    """Extract claims/evidence with two LLMs; keep only agreed claims."""

    def __init__(self, client_a: JSONChatClient, client_b: JSONChatClient | None = None) -> None:
        self._a = client_a
        self._b = client_b or _second_client()

    @traced("agent.extractor.consensus")
    async def __call__(self, state: ReasoningState) -> dict:
        doc = state["document"]
        attempts = state.get("attempts", 0)
        user = extractor_user(doc.content)
        data_a, data_b = await asyncio.gather(
            self._a.complete_json(EXTRACTOR_SYSTEM, user),
            self._b.complete_json(EXTRACTOR_SYSTEM, user),
        )
        claims_a = data_a.get("claims", []) if isinstance(data_a, dict) else []
        claims_b = data_b.get("claims", []) if isinstance(data_b, dict) else []
        agreed = agree_claims(claims_a, claims_b)
        kept_ids = {str(c.get("id")) for c in agreed}

        supported = _filter_edge_map(data_a.get("supported_by", {}), kept_ids)
        decon = _filter_edge_map(data_a.get("decontextualizes", {}), kept_ids)
        used_evidence = {e for evs in supported.values() for e in evs} | {
            e for evs in decon.values() for e in evs
        }
        evidence = [
            e for e in data_a.get("evidence", []) if str(e.get("id")) in used_evidence
        ]
        _log.info(
            "consensus_extract",
            doc=doc.id,
            a=len(claims_a),
            b=len(claims_b),
            agreed=len(agreed),
        )
        return {
            "claims": agreed,
            "evidence": evidence,
            "supported_by": supported,
            "decontextualizes": decon,
            "attempts": attempts + 1,
        }


class ConsensusRhetoricAgent:
    """Detect rhetoric with two LLMs; keep only categories both agree on."""

    def __init__(self, client_a: JSONChatClient, client_b: JSONChatClient | None = None) -> None:
        self._a = client_a
        self._b = client_b or _second_client()

    @traced("agent.rhetoric.consensus")
    async def __call__(self, state: ReasoningState) -> dict:
        doc = state["document"]
        user = rhetoric_user(doc.content)
        data_a, data_b = await asyncio.gather(
            self._a.complete_json(RHETORIC_SYSTEM, user),
            self._b.complete_json(RHETORIC_SYSTEM, user),
        )
        rhet_a = data_a.get("rhetoric", []) if isinstance(data_a, dict) else []
        rhet_b = data_b.get("rhetoric", []) if isinstance(data_b, dict) else []
        agreed = agree_rhetoric(rhet_a, rhet_b)
        employs = [r.get("id") for r in agreed if r.get("id")]
        _log.info("consensus_rhetoric", doc=doc.id, a=len(rhet_a), b=len(rhet_b), agreed=len(agreed))
        return {"rhetoric": agreed, "employs_rhetoric": employs}


def _filter_edge_map(raw: dict, kept_ids: set[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        if str(k) in kept_ids and isinstance(v, list):
            out[str(k)] = [str(x) for x in v]
    return out
