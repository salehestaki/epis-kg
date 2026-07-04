"""LangGraph multi-agent reasoning layer for Epis-KG.

A cyclic ``StateGraph`` routes a raw document through an ExtractorAgent (atomic
claims + evidence), a RhetoricAgent (fallacies / manipulation), and a
ReviewerAgent (schema validation). Validation failures loop back to extraction
for autonomous correction before anything is persisted.
"""

from agentic_reasoning.workflows.graph import build_reasoning_graph
from agentic_reasoning.state import ReasoningState

__all__ = ["build_reasoning_graph", "ReasoningState"]
