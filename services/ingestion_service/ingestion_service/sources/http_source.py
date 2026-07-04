"""Generic HTTP JSON source (News APIs, X/Twitter search, RSS-to-JSON, ...).

Configured with an endpoint and a small mapping describing where the content,
url and author live in the response. Retries transient failures.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ingestion_service.sources.base import BaseSource
from observability import get_logger

_log = get_logger("ingestion.http_source")


def _dig(obj: Any, dotted: str) -> Any:
    cur = obj
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


class HttpJSONSource(BaseSource):
    name = "http"

    def __init__(
        self,
        endpoint: str,
        *,
        items_path: str = "items",
        content_field: str = "content",
        url_field: str = "url",
        author_field: str = "author",
        platform: str | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        rate_per_sec: float = 2.0,
    ) -> None:
        super().__init__(rate_per_sec=rate_per_sec)
        self._endpoint = endpoint
        self._items_path = items_path
        self._content_field = content_field
        self._url_field = url_field
        self._author_field = author_field
        self.platform = platform
        self._headers = headers or {}
        self._params = params or {}

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=10))
    async def _fetch(self) -> Any:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self._endpoint, headers=self._headers, params=self._params)
            resp.raise_for_status()
            return resp.json()

    async def _raw_records(self) -> AsyncIterator[dict]:
        try:
            payload = await self._fetch()
        except Exception as exc:  # noqa: BLE001
            _log.error("http_fetch_failed", endpoint=self._endpoint, error=str(exc))
            return
        items = _dig(payload, self._items_path) or []
        for item in items:
            yield {
                "content": _dig(item, self._content_field),
                "url": _dig(item, self._url_field),
                "source_name": _dig(item, self._author_field) or self.name,
                "platform": self.platform,
            }
