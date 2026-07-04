"""Provider-agnostic chat client that returns parsed JSON.

Separate from the neo4j-graphrag LLM wrappers because the agents need direct,
prompt-driven structured output with retries and JSON repair. Supports
DeepSeek (default, via an OpenAI-compatible proxy), Anthropic, OpenAI, and
Ollama.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from agentic_reasoning.cache import LLMCache, cache_key
from observability import get_logger

_log = get_logger("reasoning.llm")

_JSON_BLOCK = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


class LLMError(RuntimeError):
    pass


def _extract_json(text: str) -> Any:
    """Best-effort parse: try raw, then the first {...}/[...] block."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text[text.find("\n") + 1 :] if "\n" in text else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_BLOCK.search(text)
        if match:
            return json.loads(match.group(0))
        raise LLMError(f"could not parse JSON from LLM response: {text[:200]!r}")


_DEFAULT_MODEL = {
    "deepseek": "deepseek-v4-flash",
    "anthropic": "claude-opus-4-8",
    "openai": "gpt-4o-mini",
    "ollama": "llama3.1",
}

# DeepSeek proxy defaults (OpenAI-compatible).
_DEEPSEEK_BASE_URL = "https://api.gapgpt.app/v1"


def _default_model(provider: str) -> str:
    return _DEFAULT_MODEL.get(provider, "deepseek-v4-flash")


def deepseek_key_pool() -> list[str]:
    """All configured DeepSeek keys.

    Supports a single ``DEEPSEEK_API_KEY``, numbered ``DEEPSEEK_API_KEY_1..N``,
    and/or a comma-separated ``DEEPSEEK_API_KEYS``. Rotating across several keys
    multiplies throughput and spreads per-key rate limits.
    """
    found: list[str] = []
    for name in ["DEEPSEEK_API_KEY", *[f"DEEPSEEK_API_KEY_{i}" for i in range(1, 11)]]:
        v = os.getenv(name)
        if v and v.strip():
            found.append(v.strip())
    csv = os.getenv("DEEPSEEK_API_KEYS")
    if csv:
        found.extend(k.strip() for k in csv.split(",") if k.strip())
    seen: set[str] = set()
    pool = [k for k in found if not (k in seen or seen.add(k))]
    return pool or [""]


_key_counter = 0


def _next_deepseek_key() -> str:
    """Round-robin the next key from the pool (single-event-loop safe)."""
    global _key_counter
    pool = deepseek_key_pool()
    key = pool[_key_counter % len(pool)]
    _key_counter += 1
    return key


@dataclass(frozen=True, slots=True)
class ChatSettings:
    provider: str = "deepseek"
    model: str = "deepseek-v4-flash"
    temperature: float = 0.0
    max_tokens: int = 4096

    @classmethod
    def from_env(cls) -> "ChatSettings":
        provider = os.getenv("LLM_PROVIDER", "deepseek").lower()
        # If LLM_MODEL is unset, pick a sensible default for the provider.
        model = os.getenv("LLM_MODEL") or _default_model(provider)
        return cls(provider=provider, model=model)


class JSONChatClient:
    """Async chat client returning parsed JSON objects."""

    def __init__(
        self, settings: ChatSettings | None = None, cache: LLMCache | None = None
    ) -> None:
        self._cfg = settings or ChatSettings.from_env()
        self._cache = cache if cache is not None else LLMCache()

    async def complete_json(self, system: str, user: str) -> Any:
        key = cache_key(self._cfg.provider, self._cfg.model, system, user)
        cached = await self._cache.get(key)
        if cached is not None:
            _log.info("llm_cache_hit", provider=self._cfg.provider)
            return cached
        result = await self._complete_json_uncached(system, user)
        await self._cache.set(key, result)
        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, max=15), reraise=True)
    async def _complete_json_uncached(self, system: str, user: str) -> Any:
        provider = self._cfg.provider
        if provider == "deepseek":
            text = await self._deepseek(system, user)
        elif provider == "anthropic":
            text = await self._anthropic(system, user)
        elif provider == "openai":
            text = await self._openai(system, user)
        elif provider == "ollama":
            text = await self._ollama(system, user)
        else:
            raise LLMError(f"unknown LLM_PROVIDER '{provider}'")
        return _extract_json(text)

    async def _deepseek(self, system: str, user: str) -> str:
        """DeepSeek via an OpenAI-compatible proxy (default provider).

        Provider-specific reasoning knobs are sent through ``extra_body`` so the
        OpenAI SDK forwards them verbatim without rejecting unknown kwargs. They
        are gated by EPIS_REASONING_PARAMS so they can be disabled instantly if
        the endpoint does not accept them (set it to "false"). We deliberately
        do NOT force response_format=json_object because reasoning models often
        reject it; JSON is enforced via the prompt and parsed defensively.
        """
        from openai import AsyncOpenAI

        # Reasoning models can take 60-90s per call; give the client a generous
        # read timeout so slow-but-valid completions aren't dropped. (The proxy
        # itself may still enforce its own gateway timeout.)
        client = AsyncOpenAI(
            api_key=_next_deepseek_key(),  # round-robin across all configured keys
            base_url=os.getenv("DEEPSEEK_BASE_URL", _DEEPSEEK_BASE_URL),
            timeout=float(os.getenv("DEEPSEEK_TIMEOUT", "180")),
            max_retries=0,  # tenacity handles retries; avoid compounding
        )
        extra_body: dict[str, Any] = {}
        if os.getenv("EPIS_REASONING_PARAMS", "true").lower() in ("1", "true", "yes"):
            # NOTE: `thinking` (Anthropic-style) + `reasoning_effort` (OpenAI-style)
            # per the supplied DeepSeek proxy docs. Forwarded, not validated here.
            extra_body = {
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
            }
        resp = await client.chat.completions.create(
            model=self._cfg.model,
            temperature=self._cfg.temperature,
            max_tokens=self._cfg.max_tokens,
            messages=[
                {"role": "system", "content": system + "\n\nReturn valid JSON only."},
                {"role": "user", "content": user},
            ],
            extra_body=extra_body or None,
        )
        return resp.choices[0].message.content or ""

    async def _anthropic(self, system: str, user: str) -> str:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic()
        resp = await client.messages.create(
            model=self._cfg.model,
            max_tokens=self._cfg.max_tokens,
            temperature=self._cfg.temperature,
            system=system + "\n\nRespond with valid JSON only. No prose, no code fences.",
            messages=[{"role": "user", "content": user}],
        )
        return "".join(block.text for block in resp.content if block.type == "text")

    async def _openai(self, system: str, user: str) -> str:
        from openai import AsyncOpenAI

        client = AsyncOpenAI()
        resp = await client.chat.completions.create(
            model=self._cfg.model,
            temperature=self._cfg.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return resp.choices[0].message.content or ""

    async def _ollama(self, system: str, user: str) -> str:
        import httpx

        base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base}/api/chat",
                json={
                    "model": self._cfg.model,
                    "format": "json",
                    "stream": False,
                    "options": {"temperature": self._cfg.temperature},
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]
