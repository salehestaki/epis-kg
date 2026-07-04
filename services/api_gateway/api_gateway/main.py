"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api_gateway.config import ApiSettings
from api_gateway.graph_service import GraphService
from api_gateway.retrievers import Text2CypherService, VectorCypherService
from api_gateway.routers import graph, health, ingest, metrics, query, ws
from graph_layer import Neo4jSettings, close_driver, get_async_driver
from ingestion_service.broker import RedisStreamBroker
from observability import configure_logging, get_logger

_log = get_logger("api.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings: ApiSettings = app.state.settings
    demo_mode = os.getenv("EPIS_DEMO_MODE", "false").lower() in ("1", "true", "yes")

    if demo_mode:
        from api_gateway.demo import DemoGraphService, DemoRetriever

        demo_service = DemoGraphService()
        demo_retriever = DemoRetriever(await demo_service.topology())
        app.state.driver = None
        app.state.graph_service = demo_service
        app.state.text2cypher = demo_retriever
        app.state.vector_cypher = demo_retriever
        app.state.broker = RedisStreamBroker()
        _log.info("api_started_demo", cors=settings.cors_origins)
        try:
            yield
        finally:
            _log.info("api_stopped")
        return

    neo = Neo4jSettings.from_env()
    driver = get_async_driver(neo)
    app.state.driver = driver
    app.state.graph_service = GraphService(driver, neo.database)
    app.state.text2cypher = Text2CypherService(driver, neo.database)
    app.state.vector_cypher = VectorCypherService(driver, neo.database)
    app.state.broker = RedisStreamBroker()
    _log.info("api_started", cors=settings.cors_origins)
    try:
        yield
    finally:
        await app.state.broker.close()
        await close_driver()
        _log.info("api_stopped")


def create_app() -> FastAPI:
    settings = ApiSettings()
    app = FastAPI(
        title="Epis-KG API",
        version="1.0.0",
        description="Query, visualise and score epistemic erosion in knowledge graphs.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(query.router)
    app.include_router(graph.router)
    app.include_router(metrics.router)
    app.include_router(ingest.router)
    app.include_router(ws.router)
    return app


app = create_app()
