"""Ingest documents from a local JSONL file.

Each line is a JSON object: {"content": "...", "url": "...",
"source_name": "...", "platform": "...", "a_priori_credibility": 0.4}
Also used to load the bundled sample corpus for seeding.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

from ingestion_service.sources.base import BaseSource
from observability import get_logger

_log = get_logger("ingestion.file_source")


class FileSource(BaseSource):
    name = "file"

    def __init__(self, path: str | Path, rate_per_sec: float = 50.0) -> None:
        super().__init__(rate_per_sec=rate_per_sec)
        self._path = Path(path)

    async def _raw_records(self) -> AsyncIterator[dict]:
        if not self._path.exists():
            _log.error("file_not_found", path=str(self._path))
            return
        for line in self._path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                _log.warning("bad_jsonl_line", error=str(exc))
