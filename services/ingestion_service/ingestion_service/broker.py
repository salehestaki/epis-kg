"""Redis Streams broker abstraction.

Uses a Redis Stream + consumer group so the reasoning layer can scale
horizontally with at-least-once delivery and explicit acknowledgement.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

import redis.asyncio as redis

from graph_schema import RawDocument
from observability import get_logger

_log = get_logger("ingestion.broker")

_PAYLOAD_FIELD = "payload"


class RedisStreamBroker:
    """Thin async wrapper over a single Redis Stream."""

    def __init__(
        self,
        url: str | None = None,
        stream: str | None = None,
        group: str | None = None,
    ) -> None:
        self._url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._stream = stream or os.getenv("INGESTION_STREAM", "epis-kg:ingest")
        self._group = group or os.getenv("REASONING_GROUP", "epis-kg-reasoners")
        self._redis: redis.Redis = redis.from_url(self._url, decode_responses=True)

    # -- producer ----------------------------------------------------------
    async def publish(self, doc: RawDocument) -> str:
        msg_id = await self._redis.xadd(self._stream, {_PAYLOAD_FIELD: doc.to_json()})
        _log.info("published", stream=self._stream, msg_id=msg_id, doc_id=doc.id)
        return msg_id

    async def length(self) -> int:
        return int(await self._redis.xlen(self._stream))

    # -- consumer ----------------------------------------------------------
    async def ensure_group(self) -> None:
        """Create the consumer group if it does not already exist."""
        try:
            await self._redis.xgroup_create(self._stream, self._group, id="0", mkstream=True)
            _log.info("group_created", stream=self._stream, group=self._group)
        except redis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def consume(
        self, consumer: str, block_ms: int = 5000, count: int = 10
    ) -> AsyncIterator[tuple[str, RawDocument]]:
        """Yield ``(message_id, RawDocument)`` pairs. Caller must :meth:`ack`."""
        await self.ensure_group()
        while True:
            response = await self._redis.xreadgroup(
                self._group, consumer, {self._stream: ">"}, count=count, block=block_ms
            )
            if not response:
                continue
            for _stream, messages in response:
                for msg_id, fields in messages:
                    raw = fields.get(_PAYLOAD_FIELD)
                    if raw is None:
                        await self.ack(msg_id)
                        continue
                    try:
                        yield msg_id, RawDocument.from_json(raw)
                    except Exception as exc:  # noqa: BLE001
                        _log.error("bad_payload", msg_id=msg_id, error=str(exc))
                        await self.ack(msg_id)

    async def ack(self, msg_id: str) -> None:
        await self._redis.xack(self._stream, self._group, msg_id)

    async def close(self) -> None:
        await self._redis.aclose()
