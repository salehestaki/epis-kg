"""neo4j-graphrag SimpleKGPipeline factory.

Used to transform *unstructured* text (e.g. a long article) directly into the
constrained property graph, complete with chunk embeddings and a vector index.
The multi-agent reasoning layer handles the richer rhetorical scoring path;
this pipeline is the fast lane for bulk document ingestion.
"""

from __future__ import annotations

from neo4j import AsyncDriver

from graph_layer.llm import build_embedder, build_llm
from graph_schema import build_graph_schema
from observability import get_logger

_log = get_logger("graph_layer.pipeline")


def build_kg_pipeline(driver: AsyncDriver, *, on_error: str = "IGNORE"):  # noqa: ANN201
    """Construct a SimpleKGPipeline grounded on the Epis-KG schema.

    Parameters
    ----------
    driver:
        An async Neo4j driver.
    on_error:
        Passed through to the EntityRelationExtractor. "IGNORE" keeps the
        pipeline resilient to occasional LLM formatting errors; use "RAISE"
        in tests to surface problems.
    """
    from neo4j_graphrag.experimental.components.text_splitters.fixed_size_splitter import (
        FixedSizeSplitter,
    )
    from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline

    schema = build_graph_schema()
    _log.info("build_kg_pipeline", on_error=on_error, node_types=len(schema["node_types"]))

    return SimpleKGPipeline(
        llm=build_llm(),
        driver=driver,
        embedder=build_embedder(),
        schema=schema,
        text_splitter=FixedSizeSplitter(chunk_size=1000, chunk_overlap=200),
        on_error=on_error,
        from_pdf=False,
        perform_entity_resolution=True,
    )
