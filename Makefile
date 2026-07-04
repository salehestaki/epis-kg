# Epis-KG developer entrypoints
# Requires: uv (https://docs.astral.sh/uv/), docker + docker compose, node/pnpm.

.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck test up down logs seed frontend-dev frontend-build clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Sync all Python workspace deps with uv
	uv sync --all-packages --dev

lint: ## Run ruff over all Python code
	uv run ruff check packages services

format: ## Auto-format with black + ruff --fix
	uv run black packages services
	uv run ruff check --fix packages services

typecheck: ## Static type check with mypy
	uv run mypy packages services

test: ## Run the pytest suite
	uv run pytest -q

up: ## Start the whole stack via docker compose
	docker compose up --build

down: ## Stop and remove the stack
	docker compose down

logs: ## Tail all service logs
	docker compose logs -f

seed: ## Ingest the bundled sample corpus into the graph
	docker compose exec ingestion_service python -m ingestion_service.seed

frontend-dev: ## Run the Next.js frontend in dev mode
	cd frontend && pnpm install && pnpm dev

frontend-build: ## Production build of the frontend
	cd frontend && pnpm install && pnpm build

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache **/__pycache__ frontend/.next
