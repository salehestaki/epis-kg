"""Minimal .env loader so evaluation CLIs pick up API keys automatically.

Walks up from the current working directory to find a `.env` and loads any
KEY=VALUE lines that aren't already set in the environment. No third-party
dependency; secrets are never printed.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(start: Path | None = None) -> Path | None:
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        candidate = directory / ".env"
        if candidate.exists():
            _apply(candidate)
            return candidate
    return None


def _apply(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
