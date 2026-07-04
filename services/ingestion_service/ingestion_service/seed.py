"""Seed the pipeline with the bundled sample corpus.

Usage:  python -m ingestion_service.seed  [path/to/corpus.jsonl]
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from ingestion_service.broker import RedisStreamBroker
from ingestion_service.sources import FileSource
from observability import configure_logging, get_logger

_log = get_logger("ingestion.seed")

_DEFAULT_CORPUS = Path(__file__).with_name("data") / "sample_corpus.jsonl"


async def main(path: str | None = None) -> None:
    configure_logging()
    corpus = Path(path) if path else _DEFAULT_CORPUS
    broker = RedisStreamBroker()
    source = FileSource(corpus)
    published = 0
    try:
        async for doc in source.documents():
            await broker.publish(doc)
            published += 1
    finally:
        await broker.close()
    _log.info("seed_complete", published=published, corpus=str(corpus))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else None))
