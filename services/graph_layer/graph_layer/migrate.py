"""One-off migration entrypoint: apply constraints and indexes to Neo4j.

Usage:  python -m graph_layer.migrate
"""

from __future__ import annotations

import asyncio

from graph_layer.connection import Neo4jSettings, close_driver, get_async_driver
from graph_layer.constraints import apply_constraints_and_indexes
from observability import configure_logging, get_logger

_log = get_logger("graph_layer.migrate")


async def main() -> None:
    configure_logging()
    settings = Neo4jSettings.from_env()
    driver = get_async_driver(settings)
    try:
        await driver.verify_connectivity()
        count = await apply_constraints_and_indexes(driver, settings.database)
        _log.info("migration_complete", applied=count)
    finally:
        await close_driver()


if __name__ == "__main__":
    asyncio.run(main())
