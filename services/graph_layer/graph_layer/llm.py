"""LLM and embedder factories.

Centralises provider selection so every service (reasoning, retrieval,
KG pipeline) obtains a consistently configured client. Supports Anthropic
(default), OpenAI, and Ollama (offline) through the neo4j-graphrag interfaces.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from observability import get_logger

_log = get_logger("graph_layer.llm")


@dataclass(frozen=True, slots=True)
class LLMSettings:
    provider: str = "anthropic"
    model: str = "claude-opus-4-8"
    embedding_model: str = "text-embedding-3-small"

    @classmethod
    def from_env(cls) -> "LLMSettings":
        provider = os.getenv("LLM_PROVIDER", "deepseek").lower()
        default_model = "deepseek-v4-flash" if provider == "deepseek" else "claude-opus-4-8"
        return cls(
            provider=provider,
            model=os.getenv("LLM_MODEL") or default_model,
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )


def build_llm(settings: LLMSettings | None = None):  # noqa: ANN201 - neo4j-graphrag LLMInterface
    """Return a neo4j-graphrag LLM configured to emit structured JSON output."""
    cfg = settings or LLMSettings.from_env()
    model_params = {"temperature": 0.0, "response_format": {"type": "json_object"}}
    _log.info("build_llm", provider=cfg.provider, model=cfg.model)

    if cfg.provider == "deepseek":
        from neo4j_graphrag.llm import OpenAILLM

        # DeepSeek through an OpenAI-compatible proxy: pass base_url + key to the
        # underlying OpenAI client. No forced JSON response_format (reasoning
        # models can reject it); the schema prompt enforces JSON.
        return OpenAILLM(
            model_name=cfg.model,
            model_params={"temperature": 0.0},
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.gapgpt.app/v1"),
        )
    if cfg.provider == "anthropic":
        from neo4j_graphrag.llm import AnthropicLLM

        # Anthropic uses a slightly different param surface; JSON is enforced via prompt.
        return AnthropicLLM(model_name=cfg.model, model_params={"temperature": 0.0, "max_tokens": 4096})
    if cfg.provider == "openai":
        from neo4j_graphrag.llm import OpenAILLM

        return OpenAILLM(model_name=cfg.model, model_params=model_params)
    if cfg.provider == "ollama":
        from neo4j_graphrag.llm import OllamaLLM

        return OllamaLLM(
            model_name=cfg.model,
            model_params={"temperature": 0.0, "format": "json"},
            host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
    raise ValueError(f"unknown LLM_PROVIDER '{cfg.provider}'")


def build_embedder(settings: LLMSettings | None = None):  # noqa: ANN201 - Embedder
    """Return a neo4j-graphrag embedder for chunk vectors."""
    cfg = settings or LLMSettings.from_env()
    if cfg.provider == "ollama":
        from neo4j_graphrag.embeddings import OllamaEmbeddings

        return OllamaEmbeddings(
            model=cfg.embedding_model,
            host=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        )
    # Default to OpenAI embeddings (works alongside an Anthropic chat model).
    from neo4j_graphrag.embeddings import OpenAIEmbeddings

    return OpenAIEmbeddings(model=cfg.embedding_model)
