"""Async Neo4j driver management."""

from __future__ import annotations

import os
from dataclasses import dataclass

from neo4j import AsyncDriver, AsyncGraphDatabase

from observability import get_logger

_log = get_logger("graph_layer.connection")


@dataclass(frozen=True, slots=True)
class Neo4jSettings:
    uri: str
    username: str
    password: str
    database: str = "neo4j"

    @classmethod
    def from_env(cls) -> "Neo4jSettings":
        return cls(
            uri=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
            username=os.environ.get("NEO4J_USERNAME", "neo4j"),
            password=os.environ.get("NEO4J_PASSWORD", "please-change-me"),
            database=os.environ.get("NEO4J_DATABASE", "neo4j"),
        )


_driver: AsyncDriver | None = None


def get_async_driver(settings: Neo4jSettings | None = None) -> AsyncDriver:
    """Return a process-wide singleton async driver."""
    global _driver
    if _driver is None:
        cfg = settings or Neo4jSettings.from_env()
        _log.info("neo4j_connect", uri=cfg.uri, database=cfg.database)
        _driver = AsyncGraphDatabase.driver(cfg.uri, auth=(cfg.username, cfg.password))
    return _driver


async def close_driver() -> None:
    global _driver
    if _driver is not None:
        await _driver.close()
        _driver = None
