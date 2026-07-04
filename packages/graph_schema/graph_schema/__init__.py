"""Epis-KG epistemic ontology (domain layer).

This package is the single source of truth for the shape of the knowledge
graph. Every other service imports these models so that the ingestion,
reasoning, storage and API layers cannot drift apart.
"""

from graph_schema.ontology import (
    Claim,
    ClaimContradiction,
    Document,
    Evidence,
    ExtractionResult,
    NodeLabel,
    RelationshipType,
    Rhetoric,
    RhetoricCategory,
    Source,
)
from graph_schema.payloads import RawDocument
from graph_schema.schema_def import (
    NODE_TYPES,
    RELATIONSHIP_TYPES,
    build_graph_schema,
    schema_prompt_fragment,
)

__all__ = [
    "Claim",
    "ClaimContradiction",
    "Document",
    "Evidence",
    "ExtractionResult",
    "RawDocument",
    "NodeLabel",
    "RelationshipType",
    "Rhetoric",
    "RhetoricCategory",
    "Source",
    "NODE_TYPES",
    "RELATIONSHIP_TYPES",
    "build_graph_schema",
    "schema_prompt_fragment",
]
