"""Apply Cypher constraints and indexes at startup."""

from __future__ import annotations

from pathlib import Path

from neo4j import AsyncDriver

from observability import get_logger

_log = get_logger("graph_layer.constraints")

_CYPHER_FILE = Path(__file__).with_name("constraints.cypher")


def _statements() -> list[str]:
    text = _CYPHER_FILE.read_text(encoding="utf-8")
    # Strip line comments and split on ';'
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("//")]
    body = "\n".join(lines)
    return [s.strip() for s in body.split(";") if s.strip()]


async def apply_constraints_and_indexes(driver: AsyncDriver, database: str = "neo4j") -> int:
    """Run every constraint/index statement idempotently. Returns count applied."""
    statements = _statements()
    applied = 0
    async with driver.session(database=database) as session:
        for stmt in statements:
            try:
                await session.run(stmt)  # type: ignore[arg-type]
                applied += 1
            except Exception as exc:  # noqa: BLE001
                # Vector index syntax varies across Neo4j versions; log and continue.
                _log.warning("constraint_skipped", error=str(exc), statement=stmt[:80])
    _log.info("constraints_applied", count=applied, total=len(statements))
    return applied
