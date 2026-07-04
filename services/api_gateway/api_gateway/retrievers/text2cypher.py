"""Natural-language -> read-only Cypher retrieval.

Wraps neo4j-graphrag's Text2CypherRetriever. The retriever is given the graph
schema and a handful of curated examples so it maps analytical questions
("claims with the lowest epistemic integrity about climate policy") to correct,
read-only Cypher.
"""

from __future__ import annotations

from neo4j import AsyncDriver

from graph_layer.llm import build_llm
from graph_schema import schema_prompt_fragment
from observability import get_logger, traced

_log = get_logger("api.text2cypher")

# Few-shot examples steer the LLM toward the Epis-KG vocabulary.
_EXAMPLES = [
    "USER INPUT: 'Which claims have the lowest epistemic integrity?' "
    "QUERY: MATCH (c:Claim) RETURN c.statement AS statement, "
    "c.epistemic_integrity_score AS eis ORDER BY eis ASC LIMIT 10",
    "USER INPUT: 'What rhetoric does the least credible source use?' "
    "QUERY: MATCH (s:Source)-[:PUBLISHED]->(d:Document)-[:EMPLOYS_RHETORIC]->(r:Rhetoric) "
    "RETURN s.name AS source, collect(DISTINCT r.category) AS rhetoric "
    "ORDER BY s.a_priori_credibility ASC LIMIT 10",
    "USER INPUT: 'Show contradicting claims.' "
    "QUERY: MATCH (a:Claim)-[:CONTRADICTS]->(b:Claim) "
    "RETURN a.statement AS claim_a, b.statement AS claim_b LIMIT 25",
]


class Text2CypherService:
    def __init__(self, driver: AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database
        self._retriever = None

    def _get_retriever(self):  # noqa: ANN202
        if self._retriever is None:
            from neo4j_graphrag.retrievers import Text2CypherRetriever

            self._retriever = Text2CypherRetriever(
                driver=self._driver,
                llm=build_llm(),
                neo4j_schema=schema_prompt_fragment(),
                examples=_EXAMPLES,
            )
        return self._retriever

    @traced("text2cypher.search")
    async def search(self, question: str, top_k: int = 10) -> tuple[str | None, list[dict]]:
        """Return ``(generated_cypher, records)`` for a natural-language question."""
        retriever = self._get_retriever()
        result = retriever.search(query_text=question)
        cypher = None
        metadata = getattr(result, "metadata", None) or {}
        cypher = metadata.get("cypher")
        records: list[dict] = []
        for item in getattr(result, "items", [])[:top_k]:
            content = getattr(item, "content", item)
            records.append({"content": content})
        _log.info("text2cypher", question=question[:80], hits=len(records))
        return cypher, records
