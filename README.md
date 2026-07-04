# Epis-KG — Epistemic Erosion Knowledge Graph

> A production-grade, neuro-symbolic platform that **quantifies epistemic decay** in digital
> communication networks. Epis-KG ingests text (articles, social threads), uses a cyclic
> multi-agent LLM pipeline to extract atomic claims, evidence and rhetoric, persists them into a
> Neo4j knowledge graph, and computes a mathematically rigorous **Epistemic Integrity Score** for
> every claim — then visualises the whole tension network in an interactive React Flow UI.

<p align="center"><em>Isolating "epistemic worsening": the gradual degradation of factual integrity
through emotional manipulation, decontextualisation, and logical fallacies.</em></p>

---

## Table of contents

- [Why Epis-KG](#why-epis-kg)
- [Architecture](#architecture)
- [The epistemic model](#the-epistemic-model)
- [Repository layout](#repository-layout)
- [Quick start](#quick-start)
- [Local development](#local-development)
- [API reference](#api-reference)
- [Configuration](#configuration)
- [Testing](#testing)
- [Tech stack & credits](#tech-stack--credits)
- [License](#license)

---

## Why Epis-KG

Most misinformation tooling produces an opaque "true/false" verdict from a black-box model.
Epis-KG instead makes epistemic degradation a **deterministic, mathematically quantifiable metric**
that reacts to graph topology, temporal reality and rhetorical structure. Every score is
reproducible and unit-tested; the LLM only *proposes* structure, while the math engine *decides*
integrity.

## Architecture

Four fully-decoupled layers communicate over a Redis Stream so the expensive LLM layer never
blocks high-throughput ingestion.

```
┌──────────────┐   Redis Stream   ┌───────────────────┐   Bolt    ┌──────────┐
│  Ingestion   │ ───────────────► │  Agentic Reasoning │ ────────► │  Neo4j   │
│  (sources,   │  RawDocument     │  (LangGraph cycle) │  UPSERT   │  graph   │
│  sanitise,   │                  │  extract→rhetoric→ │  + EIS    │          │
│  rate-limit) │                  │  contradiction→    │           │          │
└──────────────┘                  │  review↺           │           └────┬─────┘
                                   └───────────────────┘                │
                                             │ pub/sub graph-updates     │ read
                                             ▼                           ▼
                                   ┌───────────────────────────────────────────┐
                                   │  API Gateway (FastAPI)                      │
                                   │  /query (Text2Cypher) /graph /metrics       │
                                   │  /ingest  ws:/ws/graph                       │
                                   └───────────────────┬─────────────────────────┘
                                                       │ REST + WebSocket
                                                       ▼
                                   ┌───────────────────────────────────────────┐
                                   │  Frontend (Next.js + React Flow)            │
                                   │  animated CONTRADICTS edges, EIS bars,      │
                                   │  misinformation-hub panel, Text2Cypher bar  │
                                   └───────────────────────────────────────────┘
```

**Determinism by design.** The reasoning layer is a LangGraph `StateGraph`, not a free-form agent
chat. The `ReviewerAgent` validates every extraction against the Pydantic ontology; on failure the
graph **loops back to extraction** (up to `REASONING_MAX_ATTEMPTS`) for autonomous self-correction
before anything is written.

### The ontology

| Node       | Meaning                                   | Key properties |
|------------|-------------------------------------------|----------------|
| `Source`   | Author / user / publication               | `a_priori_credibility` |
| `Document` | Raw ingested text                         | `content`, `timestamp` |
| `Claim`    | Atomic assertion                          | `epistemic_integrity_score`, `confidence` |
| `Evidence` | Citation / statistic / quote              | `type`, `reference_url` |
| `Rhetoric` | Fallacy / emotional trigger               | `category`, `severity_weight` |

Edges: `PUBLISHED`, `CONTAINS`, `SUPPORTED_BY`, `CONTRADICTS`, `DECONTEXTUALIZES`,
`EMPLOYS_RHETORIC`.

## The epistemic model

Every claim carries an **Epistemic Integrity Score (EIS) ∈ (0, 1]**:

```
EIS = P_posterior · exp(−D)
```

- **`P_posterior`** — a Beta-Bernoulli Bayesian update anchored on the source's a-priori
  credibility, moved by supporting evidence (successes) and contradictions (failures).
- **`D`** — a composite decay penalty:

  ```
  D = α·R + β·C + γ·T
  R = 1 − exp(−Σ wᵣ · 1_active(r))     rhetorical amplification (bounded)
  C = contradictions_in / total_degree  structural contradiction density
  T = 1 − exp(−λ · age_days)            temporal staleness (BEWA half-life)
  ```

`α, β, γ, λ` are tunable via env vars. A claim that is highly contradicted, laden with active
rhetorical vulnerabilities, and left uncorroborated over time **decays toward 0**.

**Active Misinformation Hubs.** The API computes **betweenness centrality** on the claim/source
projection; a node that is simultaneously a structural bridge *and* epistemically degraded is
flagged as an Active Misinformation Hub.

All of this lives in [`packages/epistemic_math`](packages/epistemic_math) and is fully unit-tested.

## Repository layout

```
epis-kg-workspace/
├── docker-compose.yml          # full stack
├── packages/                   # shared domain libraries
│   ├── graph_schema/           # Pydantic ontology + neo4j-graphrag GraphSchema
│   ├── epistemic_math/         # Bayesian belief, decay, centrality
│   └── observability/          # structured logging + tracing
├── services/
│   ├── ingestion_service/      # sources, sanitisation, Redis Stream producer
│   ├── agentic_reasoning/      # LangGraph agents + worker
│   ├── graph_layer/            # Neo4j writer, constraints, KG pipeline
│   └── api_gateway/            # FastAPI: query/graph/metrics/ingest/ws
└── frontend/                   # Next.js + React Flow visualisation
```

## Quick start

**Prerequisites:** Docker + Docker Compose. A `DEEPSEEK_API_KEY` (default chat LLM, via an
OpenAI-compatible proxy) and an `OPENAI_API_KEY` (default embeddings) — or set
`LLM_PROVIDER=ollama` for a fully offline run.

```bash
cp .env.example .env         # then edit secrets
docker compose up --build    # starts neo4j, redis, ingestion, reasoning, api, frontend
```

Then:

- Frontend  → http://localhost:3000
- API docs  → http://localhost:8000/docs
- Neo4j     → http://localhost:7474

Seed the bundled sample corpus (a water-safety misinformation scenario):

```bash
docker compose exec ingestion_service python -m ingestion_service.seed
```

Watch the graph populate live in the frontend as the reasoning worker scores each document.

### Instant demo (no Docker, no API keys)

Want to *see it* immediately? A one-command launcher runs the API in
`EPIS_DEMO_MODE` — an in-memory water-safety misinformation scenario scored by
the **real** `epistemic_math` engine — plus the frontend:

```powershell
./run-demo.ps1      # Windows (PowerShell)
```
```bash
./run-demo.sh       # macOS / Linux / Git Bash
```

Then open **http://localhost:3000**. First run creates a venv and installs deps;
subsequent runs start instantly. This needs no Neo4j, Redis, or LLM keys.

### Offline mode (no API keys)

```bash
LLM_PROVIDER=ollama docker compose --profile offline up --build
docker compose exec ollama ollama pull llama3.1
```

## Local development

Python side uses [`uv`](https://docs.astral.sh/uv/) workspaces:

```bash
make install      # uv sync --all-packages --dev
make lint         # ruff
make typecheck    # mypy
make test         # pytest across all packages/services
```

Frontend:

```bash
make frontend-dev # cd frontend && pnpm dev
```

## API reference

| Method | Path          | Description |
|--------|---------------|-------------|
| GET    | `/health`     | Liveness |
| GET    | `/ready`      | Neo4j connectivity |
| POST   | `/query`      | Natural language → read-only Cypher (Text2Cypher) |
| GET    | `/graph`      | Full node/edge topology for the canvas |
| GET    | `/metrics`    | Counts, mean EIS, Active Misinformation Hubs |
| POST   | `/ingest`     | Queue ad-hoc text for analysis |
| WS     | `/ws/graph`   | Real-time `graph_updated` events |

## Configuration

See [`.env.example`](.env.example) for the full list. Highlights:

| Variable | Default | Meaning |
|----------|---------|---------|
| `LLM_PROVIDER` | `deepseek` | `deepseek` \| `anthropic` \| `openai` \| `ollama` |
| `LLM_MODEL` | `deepseek-v4-flash` | Chat model |
| `DEEPSEEK_BASE_URL` | `https://api.tapsage.com/deepseek/v1` | OpenAI-compatible proxy base URL |
| `EPIS_ALPHA/BETA/GAMMA` | `0.5/0.35/0.15` | Decay sensitivity weights |
| `EPIS_LAMBDA` | `0.05` | Temporal decay constant (per day) |
| `REASONING_MAX_ATTEMPTS` | `3` | Self-correction loop budget |

## Testing

```bash
uv run pytest -q
```

The suite covers the ontology contract, the full epistemic-math engine (Bayesian update, decay,
hub detection), the graph-writer parameter mapping, the **cyclic self-correction** of the reasoning
graph (with a scripted LLM), and the API endpoints (with stubbed services — no live infra needed).

## Empirical validation & research features

Epis-KG ships the tooling needed to defend its claims empirically rather than
anecdotally:

- **Ground-truth benchmarking (LIAR).** `packages/evaluation` auto-downloads the
  [LIAR](https://huggingface.co/datasets/liar) fact-checking dataset, runs each
  statement through the full pipeline, and reports **Pearson/Spearman
  correlation** and **AUC-ROC** of the EIS against the 6-point veracity scale:

  ```bash
  python -m evaluation.evaluate_eis --split test --limit 500
  ```

- **Bayesian hyperparameter optimisation.** `evaluation/tune_parameters.py` uses
  [Optuna](https://optuna.org) (TPE) to fit the decay weights (α, β, γ, λ) that
  maximise correlation with the LIAR validation split, caching the LLM signals
  once so thousands of trials cost no extra API calls. Winning weights are
  written to `epistemic_math/tuned_params.json` and loaded automatically.

  ```bash
  python -m evaluation.tune_parameters --trials 100 --limit 400
  ```

- **Multi-model consensus (hallucination mitigation).** Set
  `EPIS_CONSENSUS_MODE=true` to route extraction & rhetoric through two
  independent LLMs (an Anthropic model + an OpenAI model); only atomic claims/rhetoric that
  **both** models agree on (semantic-similarity matched) are persisted.

- **Network-driven source credibility.** `graph_layer.credibility` computes a
  personalised **PageRank/TrustRank** over `Source` nodes from their claims'
  `SUPPORTED_BY` / `CONTRADICTS` structure; the Bayesian prior anchors on this
  dynamic `pagerank_credibility` instead of hardcoded metadata.

  ```bash
  python -m graph_layer.credibility   # recompute & persist
  ```

## Tech stack & credits

- **Orchestration:** [LangGraph](https://github.com/langchain-ai/langgraph)
- **Graph + GraphRAG:** [Neo4j](https://neo4j.com) · [neo4j-graphrag](https://github.com/neo4j/neo4j-graphrag-python)
- **Backend:** FastAPI · Redis Streams · Pydantic v2 · NetworkX
- **Frontend:** Next.js · [React Flow / xyflow](https://github.com/xyflow/xyflow) · Tailwind CSS
- **Math foundations:** Bayesian Epistemology with Weighted Authority (BEWA), structural-balance
  and cognitive-cascade models.

## License

[MIT](LICENSE)
