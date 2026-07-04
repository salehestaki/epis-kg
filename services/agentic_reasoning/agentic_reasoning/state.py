"""Typed state object that flows through the LangGraph StateGraph."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from graph_schema import ExtractionResult, RawDocument


def _keep_last(_old: Any, new: Any) -> Any:
    """Reducer: later writes override earlier ones."""
    return new


def _extend(old: list[Any] | None, new: list[Any] | None) -> list[Any]:
    """Reducer: accumulate list entries across nodes."""
    return (old or []) + (new or [])


class ReasoningState(TypedDict, total=False):
    """State machine payload.

    ``total=False`` because nodes populate fields incrementally.
    """

    document: RawDocument

    # ExtractorAgent output
    claims: Annotated[list[dict], _keep_last]
    evidence: Annotated[list[dict], _keep_last]
    supported_by: Annotated[dict[str, list[str]], _keep_last]
    decontextualizes: Annotated[dict[str, list[str]], _keep_last]

    # RhetoricAgent output
    rhetoric: Annotated[list[dict], _keep_last]
    employs_rhetoric: Annotated[list[str], _keep_last]

    # Contradiction detection output
    contradictions: Annotated[list[dict], _keep_last]

    # ReviewerAgent output
    result: Annotated[ExtractionResult | None, _keep_last]
    errors: Annotated[list[str], _extend]
    attempts: Annotated[int, _keep_last]
    valid: Annotated[bool, _keep_last]
