"""Neo4j graph layer for Epis-KG.

Exposes the async driver factory, the constraint/index bootstrapper, the
epistemic graph writer (UPSERT + score recomputation), and the
neo4j-graphrag KG-construction pipeline factory.
"""

from graph_layer.connection import Neo4jSettings, close_driver, get_async_driver
from graph_layer.constraints import apply_constraints_and_indexes
from graph_layer.credibility import CredibilityService, compute_source_credibility
from graph_layer.writer import EpistemicGraphWriter

__all__ = [
    "Neo4jSettings",
    "get_async_driver",
    "close_driver",
    "apply_constraints_and_indexes",
    "EpistemicGraphWriter",
    "CredibilityService",
    "compute_source_credibility",
]
