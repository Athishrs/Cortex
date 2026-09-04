# Cortex

A Retrieval-Augmented Generation (RAG) API built with FastAPI, PostgreSQL/pgvector, Voyage AI, and Google Gemini — fully containerized, tested, and deployed via a real CI/CD pipeline into Kubernetes with Helm.

This project was built as a hands-on learning exercise to go deep on infrastructure and DevOps concepts (testing, CI/CD, Docker, Kubernetes, Helm) on top of a working RAG application, rather than just wiring up an LLM demo.

## What it does

Upload a document → it gets chunked and embedded → ask a question → the API retrieves the most relevant chunks via vector similarity search and generates a grounded answer using Gemini, citing which chunks it used.

```
POST /documents/   → upload and chunk a document, embed each chunk, store in Postgres
GET  /documents/   → list uploaded documents
DELETE /documents/{id} → delete a document (cascades to its chunks)
POST /query/        → ask a question, get a grounded answer with sources
```

## Architecture

```
Client
  │
  ▼
FastAPI (async, SQLAlchemy)
  │
  ├──► PostgreSQL + pgvector  (chunk storage, cosine similarity search)
  ├──► Voyage AI (voyage-3)    (1024-dim embeddings — document + query)
  └──► Google Gemini (gemini-3.6-flash)  (grounded answer generation)
```

**Chunking:** `RecursiveCharacterTextSplitter`, 800-char chunks with 120-char overlap, so context isn't lost at chunk boundaries.

**Retrieval:** pgvector's `<=>` cosine distance operator, ordered by similarity, top-k configurable (default 5).

**Generation:** retrieved chunks are joined into a grounded prompt that explicitly instructs the model to answer only from the provided context, or say so if it can't.

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI, async SQLAlchemy, Pydantic |
| Database | PostgreSQL 16 + pgvector |
| Embeddings | Voyage AI (`voyage-3`, 1024-dim) |
| Generation | Google Gemini (`gemini-3.6-flash`) |
| Testing | pytest, pytest-asyncio, httpx |
| CI/CD | GitHub Actions |
| Containerization | Docker |
| Orchestration | Kubernetes (Deployment, Service, ConfigMap, Secret) |
| Packaging | Helm |
| Registry | GitHub Container Registry (GHCR) |

## CI/CD pipeline

Every push to `main` runs a three-stage pipeline:

```
test  →  build  →  (deploy, manual via Helm)
44s       1m 2s
```

1. **test** — spins up a throwaway PostgreSQL + pgvector service container, creates the schema, and runs the full test suite against it.
2. **build** — builds the Docker image and pushes it to GHCR, tagged both `:latest` and by commit SHA for traceability.
3. **deploy** — `helm upgrade` rolls the new image out to the cluster with zero downtime (currently run manually against a local cluster; in a production setup this stage would target a persistent cloud cluster such as EKS/GKE).

Total pipeline time: **under 2 minutes**, end to end.

## Real, measured metrics

These are actual numbers from this project, not estimates:

- **Test suite:** 14 tests (CRUD, cascade deletes, chunking, embeddings, retrieval, generation) — 100% passing, ~1.3s full run
- **Docker image size:** 140MB (Python 3.13-slim base, layered dependency caching)
- **CI pipeline duration:** 1m 51s (test + build)
- **End-to-end query latency:** ~3.75s (embedding + vector search + generation, real API calls, no mocking)
- **Deployment:** 1 command (`helm upgrade`) with zero-downtime rolling updates, replacing what was originally 4+ manual `kubectl apply` steps

## Running locally

```bash
# 1. Start Postgres
docker run -d --name cortex-postgres -p 5433:5432 \
  -e POSTGRES_USER=cortex -e POSTGRES_PASSWORD=cortex -e POSTGRES_DB=cortex \
  pgvector/pgvector:pg16

# 2. Set up the app
cd cortex/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your Voyage and Gemini API keys

# 3. Run
uvicorn app.main:app --reload
```

Visit `http://127.0.0.1:8000/docs` for interactive API docs.

## Running the tests

```bash
pytest tests/ -v
```

External API calls (Voyage, Gemini) are mocked in tests — only your local Postgres needs to be running.

## Running via Docker

```bash
docker build -t cortex-backend .
docker run -p 8000:8000 --env-file .env \
  -e DATABASE_URL="postgresql+asyncpg://cortex:cortex@host.docker.internal:5433/cortex" \
  cortex-backend
```

## Running on Kubernetes (via Helm)

Requires a local cluster (minikube) and the image loaded/available:

```bash
helm install cortex ./cortex-chart -f ./cortex-chart/values-secret.yaml
kubectl get pods
minikube service cortex-backend-service --url
```

`values-secret.yaml` (gitignored) holds real API keys; `values.yaml` holds safe, committed defaults. See `cortex-chart/values.yaml` for all configurable options (replica count, image tag, ports).

## Known limitations / deliberate scope decisions

- **Source citations are chunk-text previews**, not real `{document, page}` references — deferred until PDF ingestion with real page structure is added.
- **Empty-question handling for `/query/`** is not explicitly validated — an intentionally deferred edge case.
- **Secrets in this repo use a local Helm values file**, appropriate for a demo project. In production, this would be backed by an external secret manager (AWS Secrets Manager, HashiCorp Vault) synced via a tool like External Secrets Operator, rather than a plain Kubernetes Secret manifest.
- **CD currently targets a local cluster.** A production setup would deploy to a persistent cloud cluster (EKS/GKE) rather than a local minikube instance.

## What I'd optimize next

Given the ~3.75s query latency, the Gemini generation call is the largest single contributor. Options worth exploring: streaming the response back to the client instead of waiting for the full generation, or trying a faster/smaller model for latency-sensitive use cases.