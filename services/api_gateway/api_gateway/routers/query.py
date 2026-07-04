"""Natural-language analytical queries via Text2Cypher."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api_gateway.dependencies import get_text2cypher, get_vector_cypher
from api_gateway.retrievers import Text2CypherService, VectorCypherService
from api_gateway.schemas import QueryRequest, QueryResponse

router = APIRouter(prefix="/query", tags=["query"])


@router.post("", response_model=QueryResponse)
async def run_query(
    body: QueryRequest,
    text2cypher: Text2CypherService = Depends(get_text2cypher),
    vector: VectorCypherService = Depends(get_vector_cypher),
) -> QueryResponse:
    retriever = vector if body.retriever == "vector" else text2cypher
    try:
        cypher, records = await retriever.search(body.question, body.top_k)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"retrieval failed: {exc}") from exc

    answer = (
        f"Found {len(records)} result(s)."
        if records
        else "No matching records for that question."
    )
    return QueryResponse(question=body.question, cypher=cypher, answer=answer, records=records)
