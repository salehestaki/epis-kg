# graph_layer is a library; this image is primarily used for running its
# migrations / one-off maintenance tasks against Neo4j.
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Shared packages first (better layer caching)
COPY packages/ packages/
COPY services/graph_layer/ services/graph_layer/
COPY pyproject.toml README.md ./

RUN uv pip install --system \
    ./packages/graph_schema \
    ./packages/epistemic_math \
    ./packages/observability \
    ./services/graph_layer

CMD ["python", "-m", "graph_layer.migrate"]
