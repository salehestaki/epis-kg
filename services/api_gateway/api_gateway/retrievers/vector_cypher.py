"""Vector + graph-traversal retrieval.

Wraps neo4j-graphrag's VectorCypherRetriever: it first finds semantically
similar chunks via the vector index, then traverses the graph from those
chunks to pull multi-hop relational context (the claims a chunk mentions, the
rhetoric attached to their documents, and the sources that published them).
This returns *reasoned context*, not just isolated text snippets.
"""

from __future__ import annotations

from neo4j import AsyncDriver

from graph_layer.llm import build_embedder
from observability import get_logger, traced

_log = get_logger("api.vector_cypher")

# From a matched chunk, walk out to the surrounding epistemic context.
_RETRIEVAL_QUERY = """
WITH node, score
MATCH (node)<-[:FROM_CHUNK]-(c:Claim)
OPTIONAL MATCH (d:Document)-[:CONTAINS]->(c)
OPTIONAL MATCH (s:Source)-[:PUBLISHED]->(d)
OPTIONAL MATCH (d)-[:EMPLOYS_RHETORIC]->(r:Rhetoric)
RETURN c.statement AS claim,
       c.epistemic_integrity_score AS eis,
       s.name AS source,
       collect(DISTINCT r.category) AS rhetoric,
       score
ORDER BY score DESC
"""


class VectorCypherService:
    def __init__(
        self,
        driver: AsyncDriver,
        database: str = "neo4j",
        index_name: str = "chunk_embedding",
    ) -> None:
        self._driver = driver
        self._database = database
        self._index_name = index_name
        self._retriever = None

    def _get_retriever(self):  # noqa: ANN202
        if self._retriever is None:
            from neo4j_graphrag.retrievers import VectorCypherRetriever

            self._retriever = VectorCypherRetriever(
                driver=self._driver,
                index_name=self._index_name,
                retrieval_query=_RETRIEVAL_QUERY,
                embedder=build_embedder(),
            )
        return self._retriever

    @traced("vector_cypher.search")
    async def search(self, question: str, top_k: int = 10) -> tuple[None, list[dict]]:
        retriever = self._get_retriever()
        result = retriever.search(query_text=question, top_k=top_k)
        records = [
            {"content": getattr(item, "content", item)}
            for item in getattr(result, "items", [])
        ]
        _log.info("vector_cypher", question=question[:80], hits=len(records))
        return None, records
