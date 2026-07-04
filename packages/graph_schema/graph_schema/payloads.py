"""Wire contracts exchanged between services over the message broker.

Kept in the shared domain package so the ingestion (producer) and reasoning
(consumer) layers cannot drift on the payload shape.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RawDocument(BaseModel):
    """A sanitised unit of text handed from ingestion to reasoning."""

    id: str = Field(..., description="Deterministic id (hash of url+content).")
    content: str
    url: str | None = None
    source_name: str = "unknown"
    source_platform: str | None = None
    # Publisher credibility if the ingestion layer already knows it.
    a_priori_credibility: float | None = None
    fetched_at: datetime = Field(default_factory=_utcnow)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str | bytes) -> "RawDocument":
        return cls.model_validate_json(raw)
