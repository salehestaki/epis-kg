"""Reasoning worker: broker -> LangGraph -> Neo4j.

Consumes RawDocuments from the Redis Stream, runs each through the cyclic
reasoning graph, and persists the validated ExtractionResult via the
EpistemicGraphWriter. Also publishes a lightweight "graph_updated" event so the
API can push real-time updates to the frontend over WebSockets.
"""

from __future__ import annotations

import asyncio
import os
import socket

from agentic_reasoning.llm_client import JSONChatClient
from agentic_reasoning.state import ReasoningState
from agentic_reasoning.workflows.graph import build_reasoning_graph
from graph_layer import (
    EpistemicGraphWriter,
    Neo4jSettings,
    apply_constraints_and_indexes,
    close_driver,
    get_async_driver,
)
from ingestion_service.broker import RedisStreamBroker
from observability import configure_logging, get_logger, traced

_log = get_logger("reasoning.worker")

UPDATE_CHANNEL = os.getenv("GRAPH_UPDATE_CHANNEL", "epis-kg:graph-updates")


class ReasoningWorker:
    def __init__(self) -> None:
        self._broker = RedisStreamBroker()
        # A checkpointer enables LangGraph time-travel debugging and
        # human-in-the-loop pauses; each document runs on its own thread_id.
        from langgraph.checkpoint.memory import MemorySaver

        self._graph = build_reasoning_graph(JSONChatClient(), checkpointer=MemorySaver())
        settings = Neo4jSettings.from_env()
        self._driver = get_async_driver(settings)
        self._writer = EpistemicGraphWriter(self._driver, settings.database)
        self._database = settings.database
        self._consumer = f"reasoner-{socket.gethostname()}-{os.getpid()}"

    async def startup(self) -> None:
        await self._driver.verify_connectivity()
        await apply_constraints_and_indexes(self._driver, self._database)
        await self._broker.ensure_group()
        _log.info("worker_ready", consumer=self._consumer)

    @traced("worker.process")
    async def process_one(self, document) -> bool:  # noqa: ANN001
        initial: ReasoningState = {"document": document, "attempts": 0, "errors": []}
        config = {"configurable": {"thread_id": document.id}}
        final = await self._graph.ainvoke(initial, config=config)
        result = final.get("result")
        if result is None:
            _log.error("no_result", doc=document.id)
            return False
        if not final.get("valid"):
            _log.warning("persisting_invalid_skipped", doc=document.id)
            return False
        claim_ids = await self._writer.write(result)
        await self._notify(document.id, claim_ids)
        return True

    async def _notify(self, doc_id: str, claim_ids: list[str]) -> None:
        try:
            await self._broker._redis.publish(  # noqa: SLF001 - intentional reuse of connection
                UPDATE_CHANNEL, f'{{"document": "{doc_id}", "claims": {len(claim_ids)}}}'
            )
        except Exception as exc:  # noqa: BLE001
            _log.warning("notify_failed", error=str(exc))

    async def run(self) -> None:
        await self.startup()
        async for msg_id, document in self._broker.consume(self._consumer):
            try:
                await self.process_one(document)
            except Exception as exc:  # noqa: BLE001
                _log.error("process_failed", doc=document.id, error=str(exc))
            finally:
                await self._broker.ack(msg_id)

    async def close(self) -> None:
        await self._broker.close()
        await close_driver()


async def main() -> None:
    configure_logging()
    worker = ReasoningWorker()
    try:
        await worker.run()
    finally:
        await worker.close()


if __name__ == "__main__":
    asyncio.run(main())
