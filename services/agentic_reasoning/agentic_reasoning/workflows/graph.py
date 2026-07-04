"""The cyclic reasoning StateGraph.

    START -> extract -> rhetoric -> contradiction -> review
                                                       |
                          valid? --------------------- +
                          |  yes -> END
                          |  no & attempts left -> extract   (self-correction loop)
                          |  no & exhausted    -> END        (persist best effort / drop)
"""

from __future__ import annotations

import os

from langgraph.graph import END, START, StateGraph

from agentic_reasoning.agents import (
    ContradictionAgent,
    ExtractorAgent,
    ReviewerAgent,
    RhetoricAgent,
)
from agentic_reasoning.llm_client import JSONChatClient
from agentic_reasoning.state import ReasoningState
from observability import get_logger

_log = get_logger("reasoning.graph")

MAX_ATTEMPTS = int(os.getenv("REASONING_MAX_ATTEMPTS", "3"))


def _consensus_enabled() -> bool:
    return os.getenv("EPIS_CONSENSUS_MODE", "false").lower() in ("1", "true", "yes")


def _route_after_review(state: ReasoningState) -> str:
    if state.get("valid"):
        return "accept"
    if state.get("attempts", 0) >= MAX_ATTEMPTS:
        _log.warning(
            "reasoning_exhausted",
            doc=state["document"].id,
            attempts=state.get("attempts"),
            errors=state.get("errors", [])[-3:],
        )
        return "give_up"
    return "retry"


def build_reasoning_graph(client: JSONChatClient | None = None, *, checkpointer=None):  # noqa: ANN201
    """Compile the reasoning graph.

    Parameters
    ----------
    client:
        Shared JSON chat client. Defaults to one built from env.
    checkpointer:
        Optional LangGraph checkpointer for time-travel debugging / HITL pauses.
    """
    client = client or JSONChatClient()

    # Consensus mode routes extraction & rhetoric through two independent LLMs
    # and keeps only what both agree on (hallucination mitigation).
    if _consensus_enabled():
        from agentic_reasoning.agents.consensus_agents import (
            ConsensusExtractorAgent,
            ConsensusRhetoricAgent,
        )

        extractor: object = ConsensusExtractorAgent(client)
        rhetoric: object = ConsensusRhetoricAgent(client)
        _log.info("consensus_mode_enabled")
    else:
        extractor = ExtractorAgent(client)
        rhetoric = RhetoricAgent(client)

    graph = StateGraph(ReasoningState)
    graph.add_node("extract", extractor)
    graph.add_node("rhetoric", rhetoric)
    graph.add_node("contradiction", ContradictionAgent(client))
    graph.add_node("review", ReviewerAgent())

    graph.add_edge(START, "extract")
    graph.add_edge("extract", "rhetoric")
    graph.add_edge("rhetoric", "contradiction")
    graph.add_edge("contradiction", "review")
    graph.add_conditional_edges(
        "review",
        _route_after_review,
        {"accept": END, "give_up": END, "retry": "extract"},
    )

    return graph.compile(checkpointer=checkpointer)
