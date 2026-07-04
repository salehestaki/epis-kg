"""Ingestion service entrypoint.

By default this seeds the bundled corpus once and then idles, keeping the
container alive so operators can exec `python -m ingestion_service.seed` or
wire up live sources. Set INGESTION_MODE=poll to periodically pull from a
configured HTTP source instead.
"""

from __future__ import annotations

import asyncio
import os

from ingestion_service.broker import RedisStreamBroker
from ingestion_service.seed import main as seed_main
from ingestion_service.sources import HttpJSONSource
from observability import configure_logging, get_logger

_log = get_logger("ingestion.main")


async def _poll_loop(interval_s: int) -> None:
    endpoint = os.environ["INGESTION_HTTP_ENDPOINT"]
    broker = RedisStreamBroker()
    source = HttpJSONSource(
        endpoint,
        items_path=os.getenv("INGESTION_ITEMS_PATH", "items"),
        content_field=os.getenv("INGESTION_CONTENT_FIELD", "content"),
        platform=os.getenv("INGESTION_PLATFORM"),
    )
    try:
        while True:
            count = 0
            async for doc in source.documents():
                await broker.publish(doc)
                count += 1
            _log.info("poll_cycle", published=count)
            await asyncio.sleep(interval_s)
    finally:
        await broker.close()


async def main() -> None:
    configure_logging()
    mode = os.getenv("INGESTION_MODE", "seed").lower()
    _log.info("ingestion_start", mode=mode)
    if mode == "poll":
        await _poll_loop(int(os.getenv("INGESTION_POLL_INTERVAL", "300")))
    else:
        if os.getenv("INGESTION_SEED_ON_START", "true").lower() == "true":
            await seed_main()
        # Idle so the container stays up.
        while True:
            await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
