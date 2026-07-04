"""Semantic / exact caching for LLM completions.

Redundant extraction and rhetoric queries (e.g. re-ingesting the same document,
or retrying after a downstream failure) are common and expensive. This cache
keys completions on a hash of (provider, model, system, user) and stores them
either in-process (bounded LRU) or in Redis (shared across worker replicas,
with a TTL), controlled by ``EPIS_LLM_CACHE`` / ``REDIS_URL``.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import OrderedDict
from typing import Any

from observability import get_logger

_log = get_logger("reasoning.cache")


def cache_key(provider: str, model: str, system: str, user: str) -> str:
    h = hashlib.sha256()
    for part in (provider, model, system, user):
        h.update(part.encode("utf-8"))
        h.update(b"\x00")
    return "epis-kg:llmcache:" + h.hexdigest()


class LLMCache:
    """Exact-match cache with an in-process LRU and optional Redis backing."""

    def __init__(self, max_size: int = 512, ttl_seconds: int = 86_400) -> None:
        self._enabled = os.getenv("EPIS_LLM_CACHE", "true").lower() in ("1", "true", "yes")
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._local: OrderedDict[str, Any] = OrderedDict()
        self._redis = self._maybe_redis()

    @staticmethod
    def _maybe_redis():  # noqa: ANN205
        url = os.getenv("REDIS_URL")
        if not url:
            return None
        try:
            import redis.asyncio as redis

            return redis.from_url(url, decode_responses=True)
        except Exception as exc:  # noqa: BLE001
            _log.warning("cache_redis_unavailable", error=str(exc))
            return None

    async def get(self, key: str) -> Any | None:
        if not self._enabled:
            return None
        if key in self._local:
            self._local.move_to_end(key)
            return self._local[key]
        if self._redis is not None:
            try:
                raw = await self._redis.get(key)
            except Exception as exc:  # noqa: BLE001
                _log.warning("cache_get_failed", error=str(exc))
                return None
            if raw:
                value = json.loads(raw)
                self._store_local(key, value)
                return value
        return None

    async def set(self, key: str, value: Any) -> None:
        if not self._enabled:
            return
        self._store_local(key, value)
        if self._redis is not None:
            try:
                await self._redis.set(key, json.dumps(value), ex=self._ttl)
            except Exception as exc:  # noqa: BLE001
                _log.warning("cache_set_failed", error=str(exc))

    def _store_local(self, key: str, value: Any) -> None:
        self._local[key] = value
        self._local.move_to_end(key)
        while len(self._local) > self._max_size:
            self._local.popitem(last=False)
