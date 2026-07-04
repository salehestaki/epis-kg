FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY packages/ packages/
COPY services/graph_layer/ services/graph_layer/
COPY services/ingestion_service/ services/ingestion_service/
COPY services/api_gateway/ services/api_gateway/

RUN uv pip install --system \
    ./packages/graph_schema \
    ./packages/epistemic_math \
    ./packages/observability \
    ./services/graph_layer \
    ./services/ingestion_service \
    ./services/api_gateway

EXPOSE 8000
CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
