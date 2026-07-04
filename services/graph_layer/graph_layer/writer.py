"""Epistemic graph writer.

Persists a validated :class:`ExtractionResult` into Neo4j using idempotent
MERGE (UPSERT) semantics, then recomputes the Epistemic Integrity Score for
every affected claim from the *current* graph topology (evidence support,
contradiction in-degree, total degree, rhetoric, age).
"""

from __future__ import annotations

from datetime import datetime, timezone

from neo4j import AsyncDriver

from epistemic_math import (
    ClaimSignals,
    RhetoricSignal,
    epistemic_integrity_score,
    load_params,
)
from graph_schema import ExtractionResult, RhetoricCategory
from graph_schema.ontology import ACTIVE_VULNERABILITIES
from observability import get_logger, traced

_log = get_logger("graph_layer.writer")

_UPSERT_CYPHER = """
// --- Source & Document ----------------------------------------------------
MERGE (s:Source {id: $source.id})
  SET s.name = $source.name,
      s.platform = $source.platform,
      s.a_priori_credibility = $source.a_priori_credibility
MERGE (d:Document {id: $document.id})
  SET d.url = $document.url,
      d.content = $document.content,
      d.timestamp = $document.timestamp
MERGE (s)-[:PUBLISHED]->(d)

// --- Claims + CONTAINS ----------------------------------------------------
WITH d
UNWIND $claims AS claim
  MERGE (c:Claim {id: claim.id})
    SET c.statement = claim.statement,
        c.confidence = claim.confidence,
        c.created_at = claim.created_at,
        c.epistemic_integrity_score =
            coalesce(c.epistemic_integrity_score, claim.epistemic_integrity_score)
  MERGE (d)-[:CONTAINS]->(c)

// --- Evidence -------------------------------------------------------------
WITH d
UNWIND $evidence AS ev
  MERGE (e:Evidence {id: ev.id})
    SET e.type = ev.type, e.reference_url = ev.reference_url, e.excerpt = ev.excerpt

// --- Rhetoric + EMPLOYS_RHETORIC ------------------------------------------
WITH d
UNWIND $rhetoric AS rh
  MERGE (r:Rhetoric {id: rh.id})
    SET r.category = rh.category, r.severity_weight = rh.severity_weight
  MERGE (d)-[:EMPLOYS_RHETORIC]->(r)

// --- SUPPORTED_BY ---------------------------------------------------------
WITH 1 AS _
UNWIND $supported_by AS link
  MATCH (c:Claim {id: link.claim_id})
  MATCH (e:Evidence {id: link.evidence_id})
  MERGE (c)-[:SUPPORTED_BY]->(e)

// --- DECONTEXTUALIZES -----------------------------------------------------
WITH 1 AS _
UNWIND $decontextualizes AS link
  MATCH (c:Claim {id: link.claim_id})
  MATCH (e:Evidence {id: link.evidence_id})
  MERGE (c)-[:DECONTEXTUALIZES]->(e)

// --- CONTRADICTS ----------------------------------------------------------
WITH 1 AS _
UNWIND $contradictions AS con
  MATCH (a:Claim {id: con.source_claim_id})
  MATCH (b:Claim {id: con.target_claim_id})
  MERGE (a)-[rel:CONTRADICTS]->(b)
    SET rel.rationale = con.rationale,
        rel.semantic_distance = con.semantic_distance
"""

# Pull every signal the decay model needs for a single claim, in one round-trip.
_SIGNALS_CYPHER = """
MATCH (c:Claim {id: $claim_id})
OPTIONAL MATCH (src:Source)-[:PUBLISHED]->(:Document)-[:CONTAINS]->(c)
OPTIONAL MATCH (c)-[:SUPPORTED_BY]->(ev:Evidence)
OPTIONAL MATCH (other:Claim)-[:CONTRADICTS]->(c)
OPTIONAL MATCH (:Document)-[:CONTAINS]->(c)<-[:CONTAINS]-(doc:Document)
OPTIONAL MATCH (doc2:Document)-[:CONTAINS]->(c)
OPTIONAL MATCH (doc2)-[:EMPLOYS_RHETORIC]->(rh:Rhetoric)
WITH c,
     max(coalesce(src.pagerank_credibility, src.a_priori_credibility, 0.5)) AS credibility,
     count(DISTINCT ev) AS n_support,
     count(DISTINCT other) AS contra_in,
     collect(DISTINCT {category: rh.category, weight: rh.severity_weight}) AS rhetoric,
     min(doc2.timestamp) AS first_seen
RETURN credibility, n_support, contra_in, rhetoric, first_seen,
       size([ (c)--() | 1 ]) AS total_degree
"""

_SET_EIS_CYPHER = "MATCH (c:Claim {id: $claim_id}) SET c.epistemic_integrity_score = $eis"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class EpistemicGraphWriter:
    """Writes extraction results and keeps the EIS coherent with the topology."""

    def __init__(self, driver: AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._database = database
        self._params = load_params()

    @traced("graph_layer.write_extraction")
    async def write(self, result: ExtractionResult) -> list[str]:
        """Persist an extraction result and rescore its claims.

        Returns the list of claim ids whose EIS was (re)computed.
        """
        errors = result.validate_referential_integrity()
        if errors:
            raise ValueError(f"cannot persist invalid extraction: {errors}")

        params = self._to_cypher_params(result)
        async with self._driver.session(database=self._database) as session:
            await session.run(_UPSERT_CYPHER, params)  # type: ignore[arg-type]

        claim_ids = [c.id for c in result.claims]
        # Contradictions can also change the score of previously-stored targets.
        for con in result.contradictions:
            if con.target_claim_id not in claim_ids:
                claim_ids.append(con.target_claim_id)

        for claim_id in claim_ids:
            await self.recompute_score(claim_id)
        _log.info("extraction_written", document=result.document.id, claims=len(claim_ids))
        return claim_ids

    @traced("graph_layer.recompute_score")
    async def recompute_score(self, claim_id: str) -> float:
        """Recompute and persist the EIS for one claim from live topology."""
        async with self._driver.session(database=self._database) as session:
            record = await (await session.run(_SIGNALS_CYPHER, claim_id=claim_id)).single()
            if record is None:
                raise KeyError(f"claim '{claim_id}' not found")

            rhetoric_signals: list[RhetoricSignal] = []
            for item in record["rhetoric"]:
                cat = item.get("category")
                if cat is None:
                    continue
                is_active = _category_is_active(cat)
                weight = item.get("weight")
                rhetoric_signals.append(
                    RhetoricSignal(
                        severity_weight=float(weight if weight is not None else 0.5),
                        is_active_vulnerability=is_active,
                    )
                )

            signals = ClaimSignals(
                a_priori_credibility=float(record["credibility"]),
                n_support=int(record["n_support"]),
                contradictions_in_degree=int(record["contra_in"]),
                total_degree=int(record["total_degree"]),
                age_days=_age_days(record["first_seen"]),
                rhetoric=rhetoric_signals,
            )
            eis = epistemic_integrity_score(signals, self._params)
            await session.run(_SET_EIS_CYPHER, claim_id=claim_id, eis=eis)
        return eis

    def _to_cypher_params(self, result: ExtractionResult) -> dict:
        supported = [
            {"claim_id": cid, "evidence_id": ev}
            for cid, evs in result.supported_by.items()
            for ev in evs
        ]
        decontext = [
            {"claim_id": cid, "evidence_id": ev}
            for cid, evs in result.decontextualizes.items()
            for ev in evs
        ]
        return {
            "source": {
                "id": result.source.id,
                "name": result.source.name,
                "platform": result.source.platform,
                "a_priori_credibility": result.source.a_priori_credibility,
            },
            "document": {
                "id": result.document.id,
                "url": result.document.url,
                "content": result.document.content,
                "timestamp": _iso(result.document.timestamp),
            },
            "claims": [
                {
                    "id": c.id,
                    "statement": c.statement,
                    "confidence": c.confidence,
                    "epistemic_integrity_score": c.epistemic_integrity_score,
                    "created_at": _iso(c.created_at),
                }
                for c in result.claims
            ],
            "evidence": [
                {"id": e.id, "type": e.type, "reference_url": e.reference_url, "excerpt": e.excerpt}
                for e in result.evidence
            ],
            "rhetoric": [
                {"id": r.id, "category": r.category.value, "severity_weight": r.severity_weight}
                for r in result.rhetoric
            ],
            "supported_by": supported,
            "decontextualizes": decontext,
            "contradictions": [
                {
                    "source_claim_id": c.source_claim_id,
                    "target_claim_id": c.target_claim_id,
                    "rationale": c.rationale,
                    "semantic_distance": c.semantic_distance,
                }
                for c in result.contradictions
            ],
        }


def _category_is_active(category_value: str) -> bool:
    try:
        return RhetoricCategory(category_value) in ACTIVE_VULNERABILITIES
    except ValueError:
        return False


def _age_days(first_seen: str | None) -> float:
    if not first_seen:
        return 0.0
    try:
        seen = datetime.fromisoformat(first_seen)
    except ValueError:
        return 0.0
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - seen
    return max(delta.total_seconds() / 86400.0, 0.0)
