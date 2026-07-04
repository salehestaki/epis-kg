"""neo4j-graphrag GraphSchema projection of the epistemic ontology.

``neo4j-graphrag``'s ``SimpleKGPipeline`` grounds the LLM by injecting a
schema describing the permitted node labels, their properties and the
relationship types. We derive that schema from the same enums used by the
Pydantic models so the two can never diverge.
"""

from __future__ import annotations

from typing import Any

from graph_schema.ontology import NodeLabel, RelationshipType, RhetoricCategory

# The property definitions mirror the ontology tables in the design doc.
NODE_TYPES: list[dict[str, Any]] = [
    {
        "label": NodeLabel.DOCUMENT.value,
        "properties": [
            {"name": "id", "type": "STRING"},
            {"name": "url", "type": "STRING"},
            {"name": "timestamp", "type": "STRING"},
            {"name": "content", "type": "STRING"},
        ],
    },
    {
        "label": NodeLabel.SOURCE.value,
        "properties": [
            {"name": "id", "type": "STRING"},
            {"name": "name", "type": "STRING"},
            {"name": "platform", "type": "STRING"},
            {"name": "a_priori_credibility", "type": "FLOAT"},
        ],
    },
    {
        "label": NodeLabel.CLAIM.value,
        "properties": [
            {"name": "id", "type": "STRING"},
            {"name": "statement", "type": "STRING"},
            {"name": "epistemic_integrity_score", "type": "FLOAT"},
            {"name": "confidence", "type": "FLOAT"},
        ],
    },
    {
        "label": NodeLabel.EVIDENCE.value,
        "properties": [
            {"name": "id", "type": "STRING"},
            {"name": "type", "type": "STRING"},
            {"name": "reference_url", "type": "STRING"},
        ],
    },
    {
        "label": NodeLabel.RHETORIC.value,
        "properties": [
            {"name": "id", "type": "STRING"},
            {"name": "category", "type": "STRING"},
            {"name": "severity_weight", "type": "FLOAT"},
        ],
    },
]

RELATIONSHIP_TYPES: list[dict[str, str]] = [
    {"label": RelationshipType.PUBLISHED.value},
    {"label": RelationshipType.CONTAINS.value},
    {"label": RelationshipType.SUPPORTED_BY.value},
    {"label": RelationshipType.CONTRADICTS.value},
    {"label": RelationshipType.DECONTEXTUALIZES.value},
    {"label": RelationshipType.EMPLOYS_RHETORIC.value},
]

# Which (source, rel, target) triples are legal. Passed to SimpleKGPipeline
# as `patterns` to further constrain the extraction.
PATTERNS: list[tuple[str, str, str]] = [
    (NodeLabel.SOURCE.value, RelationshipType.PUBLISHED.value, NodeLabel.DOCUMENT.value),
    (NodeLabel.DOCUMENT.value, RelationshipType.CONTAINS.value, NodeLabel.CLAIM.value),
    (NodeLabel.CLAIM.value, RelationshipType.SUPPORTED_BY.value, NodeLabel.EVIDENCE.value),
    (NodeLabel.CLAIM.value, RelationshipType.CONTRADICTS.value, NodeLabel.CLAIM.value),
    (NodeLabel.CLAIM.value, RelationshipType.DECONTEXTUALIZES.value, NodeLabel.EVIDENCE.value),
    (NodeLabel.DOCUMENT.value, RelationshipType.EMPLOYS_RHETORIC.value, NodeLabel.RHETORIC.value),
]


def build_graph_schema() -> dict[str, Any]:
    """Return the dict consumed by ``SimpleKGPipeline(schema=...)``."""
    return {
        "node_types": NODE_TYPES,
        "relationship_types": RELATIONSHIP_TYPES,
        "patterns": PATTERNS,
        "additional_node_types": False,
        "additional_relationship_types": False,
    }


def schema_prompt_fragment() -> str:
    """A compact, human/LLM-readable description of the schema.

    Injected into extraction prompts. Grounds the model so it cannot
    hallucinate node labels or relationship types.
    """
    node_lines = []
    for nt in NODE_TYPES:
        props = ", ".join(p["name"] for p in nt["properties"])
        node_lines.append(f"  - {nt['label']}({props})")
    pattern_lines = [f"  - ({s})-[:{r}]->({t})" for s, r, t in PATTERNS]
    categories = ", ".join(c.value for c in RhetoricCategory)
    return (
        "NODES (use ONLY these labels and properties):\n"
        + "\n".join(node_lines)
        + "\n\nRELATIONSHIPS (use ONLY these directed patterns):\n"
        + "\n".join(pattern_lines)
        + "\n\nRhetoric.category MUST be one of:\n  "
        + categories
    )
