FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Shared packages and upstream services this worker imports
COPY packages/ packages/
COPY services/graph_layer/ services/graph_layer/
COPY services/ingestion_service/ services/ingestion_service/
COPY services/agentic_reasoning/ services/agentic_reasoning/

RUN uv pip install --system \
    ./packages/graph_schema \
    ./packages/epistemic_math \
    ./packages/observability \
    ./services/graph_layer \
    ./services/ingestion_service \
    ./services/agentic_reasoning

CMD ["python", "-m", "agentic_reasoning.worker"]
