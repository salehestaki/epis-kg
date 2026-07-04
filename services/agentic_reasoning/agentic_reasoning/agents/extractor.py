"""ExtractorAgent: raw document -> atomic claims + evidence."""

from __future__ import annotations

from agentic_reasoning.llm_client import JSONChatClient
from agentic_reasoning.prompts import EXTRACTOR_SYSTEM, extractor_user
from agentic_reasoning.state import ReasoningState
from observability import get_logger, traced

_log = get_logger("reasoning.extractor")


class ExtractorAgent:
    def __init__(self, client: JSONChatClient) -> None:
        self._client = client

    @traced("agent.extractor")
    async def __call__(self, state: ReasoningState) -> dict:
        doc = state["document"]
        attempts = state.get("attempts", 0)
        feedback = ""
        if state.get("errors"):
            feedback = (
                "\n\nA previous attempt failed validation with these errors; fix them:\n- "
                + "\n- ".join(state["errors"][-6:])
            )
        data = await self._client.complete_json(
            EXTRACTOR_SYSTEM, extractor_user(doc.content) + feedback
        )
        claims = data.get("claims", []) if isinstance(data, dict) else []
        _log.info("extracted", doc=doc.id, claims=len(claims), attempt=attempts + 1)
        return {
            "claims": claims,
            "evidence": data.get("evidence", []),
            "supported_by": data.get("supported_by", {}),
            "decontextualizes": data.get("decontextualizes", {}),
            "attempts": attempts + 1,
        }
