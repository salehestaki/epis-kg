"""Base class for ingestion sources with built-in rate limiting."""

from __future__ import annotations

import abc
import asyncio
import time
from collections.abc import AsyncIterator

from graph_schema import RawDocument
from ingestion_service.sanitize import content_id, sanitize
from observability import get_logger

_log = get_logger("ingestion.source")


class RateLimiter:
    """Simple async token-bucket-ish limiter: at most `rate` events/second."""

    def __init__(self, rate_per_sec: float) -> None:
        self._min_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
        self._last = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        if self._min_interval <= 0:
            return
        async with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self._min_interval:
                await asyncio.sleep(self._min_interval - delta)
            self._last = time.monotonic()


class BaseSource(abc.ABC):
    """A source produces sanitised RawDocuments."""

    name: str = "base"
    platform: str | None = None

    def __init__(self, rate_per_sec: float = 5.0) -> None:
        self._limiter = RateLimiter(rate_per_sec)

    @abc.abstractmethod
    def _raw_records(self) -> AsyncIterator[dict]:
        """Yield provider-specific dicts with at least a 'content' key."""
        raise NotImplementedError

    async def documents(self) -> AsyncIterator[RawDocument]:
        async for record in self._raw_records():
            await self._limiter.wait()
            content = sanitize(str(record.get("content", "")))
            if not content:
                continue
            url = record.get("url")
            yield RawDocument(
                id=content_id(content, url),
                content=content,
                url=url,
                source_name=record.get("source_name", self.name),
                source_platform=record.get("platform", self.platform),
                a_priori_credibility=record.get("a_priori_credibility"),
            )
