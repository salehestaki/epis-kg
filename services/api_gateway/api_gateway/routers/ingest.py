"""Trigger ingestion of ad-hoc text through the API."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api_gateway.dependencies import get_broker
from api_gateway.schemas import IngestRequest, IngestResponse
from graph_schema import RawDocument
from ingestion_service.broker import RedisStreamBroker
from ingestion_service.sanitize import content_id, sanitize

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("", response_model=IngestResponse, status_code=202)
async def ingest(
    body: IngestRequest,
    broker: RedisStreamBroker = Depends(get_broker),
) -> IngestResponse:
    content = sanitize(body.content)
    doc = RawDocument(
        id=content_id(content, body.url),
        content=content,
        url=body.url,
        source_name=body.source_name,
        source_platform=body.source_platform,
        a_priori_credibility=body.a_priori_credibility,
    )
    msg_id = await broker.publish(doc)
    return IngestResponse(document_id=doc.id, queued_message_id=msg_id)
