"""RhetoricAgent: detect fallacies and emotional-manipulation markers."""

from __future__ import annotations

from agentic_reasoning.llm_client import JSONChatClient
from agentic_reasoning.prompts import RHETORIC_SYSTEM, rhetoric_user
from agentic_reasoning.state import ReasoningState
from observability import get_logger, traced

_log = get_logger("reasoning.rhetoric")


class RhetoricAgent:
    def __init__(self, client: JSONChatClient) -> None:
        self._client = client

    @traced("agent.rhetoric")
    async def __call__(self, state: ReasoningState) -> dict:
        doc = state["document"]
        data = await self._client.complete_json(RHETORIC_SYSTEM, rhetoric_user(doc.content))
        rhetoric = data.get("rhetoric", []) if isinstance(data, dict) else []
        employs = data.get("employs_rhetoric") or [r.get("id") for r in rhetoric if r.get("id")]
        _log.info("rhetoric_detected", doc=doc.id, count=len(rhetoric))
        return {"rhetoric": rhetoric, "employs_rhetoric": employs}
