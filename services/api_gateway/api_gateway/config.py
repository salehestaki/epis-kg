"""API gateway configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:3000")
    return [o.strip() for o in raw.split(",") if o.strip()]


@dataclass(frozen=True, slots=True)
class ApiSettings:
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))
    cors_origins: list[str] = field(default_factory=_origins)
    update_channel: str = os.getenv("GRAPH_UPDATE_CHANNEL", "epis-kg:graph-updates")
