FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY packages/graph_schema/ packages/graph_schema/
COPY packages/observability/ packages/observability/
COPY services/ingestion_service/ services/ingestion_service/

RUN uv pip install --system \
    ./packages/graph_schema \
    ./packages/observability \
    ./services/ingestion_service

CMD ["python", "-m", "ingestion_service.main"]
