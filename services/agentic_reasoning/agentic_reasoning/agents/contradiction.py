"""ContradictionAgent: flag CONTRADICTS edges among the extracted claims.

Uses the LLM for semantic judgement. When only one claim exists there is
nothing to compare, so the node short-circuits.
"""

from __future__ import annotations

from agentic_reasoning.llm_client import JSONChatClient
from agentic_reasoning.prompts import CONTRADICTION_SYSTEM, contradiction_user
from agentic_reasoning.state import ReasoningState
from observability import get_logger, traced

_log = get_logger("reasoning.contradiction")


class ContradictionAgent:
    def __init__(self, client: JSONChatClient) -> None:
        self._client = client

    @traced("agent.contradiction")
    async def __call__(self, state: ReasoningState) -> dict:
        claims = state.get("claims", [])
        if len(claims) < 2:
            return {"contradictions": []}
        data = await self._client.complete_json(
            CONTRADICTION_SYSTEM, contradiction_user(claims)
        )
        contradictions = data.get("contradictions", []) if isinstance(data, dict) else []
        _log.info("contradictions", doc=state["document"].id, count=len(contradictions))
        return {"contradictions": contradictions}
