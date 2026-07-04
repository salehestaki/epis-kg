"""WebSocket endpoint pushing real-time graph-update events to the frontend.

Subscribes to the Redis pub/sub channel the reasoning worker publishes to
whenever it persists a new document, and relays those events to the browser so
React Flow can re-hydrate.
"""

from __future__ import annotations

import asyncio

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from observability import get_logger

_log = get_logger("api.ws")

router = APIRouter()


@router.websocket("/ws/graph")
async def graph_updates(websocket: WebSocket) -> None:
    await websocket.accept()
    settings = websocket.app.state.settings
    broker = websocket.app.state.broker
    client: redis.Redis = broker._redis  # noqa: SLF001 - reuse configured connection
    pubsub = client.pubsub()
    await pubsub.subscribe(settings.update_channel)
    _log.info("ws_connected", channel=settings.update_channel)
    try:
        await websocket.send_json({"type": "connected", "channel": settings.update_channel})
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                await websocket.send_json({"type": "graph_updated", "data": message["data"]})
            else:
                # keepalive / yield control
                await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        _log.info("ws_disconnected")
    except Exception as exc:  # noqa: BLE001
        _log.warning("ws_error", error=str(exc))
    finally:
        await pubsub.unsubscribe(settings.update_channel)
        await pubsub.aclose()
