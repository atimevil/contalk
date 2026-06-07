# Architecture

**Analysis Date:** 2026-06-02

## Pattern Overview

**Overall:** Layered FastAPI backend (API → Service → Model) with an asynchronous task pipeline (Celery + Redis) for long-running AI analysis, a separate self-contained AI package (`backend/ai/`), and a React SPA frontend that polls for results.

**Key Characteristics:**
- Async-first backend: SQLAlchemy 2.0 async + asyncpg, async route handlers, async service functions
- Offload heavy work: upload returns `202 Accepted` immediately; AI pipeline runs in a Celery worker
- AI package isolation: `backend/ai/` exposes a single sync entry point `run_full_pipeline()` and never imports `app.*` (clean dependency direction)
- Convention-driven serialization: all responses auto-wrapped (`{success, data, disclaimer}`) and auto-camelCased

## Layers

**API / Routing Layer:**
- Purpose: HTTP endpoints, request validation, auth, error mapping
- Location: `backend/app/api/v1/` (`auth.py`, `analysis.py`, `payments.py`, `market.py`)
- Routers mounted with prefix `/api/v1` in `backend/app/main.py:182-185`; `auth`/`market`/`payment` carry their own sub-prefix, `analysis` does not (paths are `/analysis/...`, `/user/...`)
- Depends on: services layer, schemas, `core.dependencies`
- Used by: frontend via `frontend/src/api/*`

**Service Layer:**
- Purpose: business logic, external integration, DB access
- Location: `backend/app/services/` — `contract_service.py`, `auth_service.py`, `payment_service.py`, `market_service.py`, `s3_service.py`, `pdf_service.py`
- Depends on: models, schemas, external APIs (OpenAI handled in `ai/`, MOLIT/PortOne/OAuth here)
- Used by: API layer and Celery tasks

**Model / Persistence Layer:**
- Purpose: SQLAlchemy ORM entities + async engine/session
- Location: `backend/app/models/` (`user.py`, `contract.py`, `payment.py`, `quota.py`, `special_clause.py`); engine in `backend/app/core/database.py`
- Migrations: `backend/migrations/versions/` (Alembic) — `001_initial_schema.py`, `002_add_market_queries.py`

**Task / Worker Layer:**
- Purpose: async orchestration of the analysis pipeline
- Location: `backend/app/tasks/` (`celery_app.py`, `analysis.py`)
- Celery config: JSON serializer, `Asia/Seoul`, `task_acks_late=True`, `worker_prefetch_multiplier=1`, soft/hard time limits 120s/180s (`celery_app.py:11`)

**AI Pipeline Layer:**
- Purpose: OCR → clause parse → risk classify → RAG explanation
- Location: `backend/ai/` (`pipeline.py` entry, `ocr.py`, `clause_parser.py`, `classifier.py`, `rag.py`, `prompts.py`, `vectordb_builder.py`, `train.py`)
- Depends on: OpenAI, ChromaDB, transformers/torch, boto3, pdfplumber/pymupdf
- Used by: `backend/app/tasks/analysis.py` (imports `from ai.pipeline import run_full_pipeline`)

**Frontend Layer:**
- Purpose: React SPA — upload, polling, result/report rendering
- Location: `frontend/src/` (`pages/`, `components/`, `api/`, `context/`, `types/`)

## Data Flow

**Primary flow — contract upload → analysis → result (the core request flow):**

1. Frontend `POST /api/v1/analysis/upload` (multipart file) — `analysis.py:63`
2. Handler validates content-type (jpeg/png/pdf) and size (≤20MB), consumes user quota (`contract_service.check_and_consume_quota`)
3. File uploaded to S3 (or local fallback) → `Contract` row created with `status="uploaded"`, fresh `job_id` (`analysis.py:101`)
4. Celery task dispatched: `run_analysis_task.delay(contract_id, job_id, s3_key)` (`analysis.py:108`)
5. Handler returns `202` with `{jobId, status:"queued", estimatedSeconds:60}` — `UploadResponse`
6. Celery worker runs `run_analysis_task` → single `asyncio.run(_run_analysis_coro(...))` (`tasks/analysis.py:278`)
7. Coro updates `Contract.status` progressively: `ocr`(20%) → `analyzing`(50%) → calls AI pipeline → `generating`(80%) → `completed`(100%) with a new `report_id`
8. AI pipeline `run_full_pipeline(contract_id, s3_key)` (`ai/pipeline.py:37`): S3 download → OCR → detect contract type (전세/월세) → parse clauses → classify risk → parallel RAG (ThreadPoolExecutor max_workers=5) for high/medium/caution clauses only
9. Pipeline result converted to DB shape (`_convert_pipeline_result`) and stored in `Contract.result` (JSONB)
10. Frontend polls `GET /api/v1/analysis/{jobId}/status` until `completed`, then fetches `GET /api/v1/analysis/{reportId}/result`

**State Management:**
- Server-side: analysis state lives entirely on the `contracts` row (`status`, `progress`, `current_step`, `completed_steps` JSONB, `result` JSONB, `report_id`)
- Client-side: react-query for server state (`App.tsx` QueryClient, `staleTime` 1min, `retry` 1); React Context for auth and toasts (`frontend/src/context/`)

**Market-price flow:** Frontend → `GET /api/v1/market/...` → `market_service.py` → parallel multi-month MOLIT XML fetches → aggregated 전세/월세 stats.

## Key Abstractions

**`run_full_pipeline()` (sync facade):**
- Purpose: single stable interface between backend and the AI package
- Location: `backend/ai/pipeline.py:37`
- Pattern: synchronous function returning a fully-specified result dict; backend calls it via `loop.run_in_executor` so it never blocks the event loop

**`CamelModel` (response convention base):**
- Purpose: snake_case Python ↔ camelCase JSON for TS compatibility
- Location: `backend/app/schemas/common.py:10` (`alias_generator=to_camel`, `populate_by_name=True`, `from_attributes=True`)

**`AliasRoute` (custom APIRoute):**
- Purpose: force `response_model_by_alias=True` on every route (BUG-001 fix)
- Location: `backend/app/main.py:20`, set as `default_route_class`

**Success-wrapper middleware:**
- Purpose: wrap all 2xx JSON into `{success:true, data, disclaimer}` unless already wrapped
- Location: `backend/app/main.py:95` (`wrap_success_response`); excludes `/health`, `/docs`, `/redoc`, `/openapi`, `/api/v1/health`, and `*/pdf` (binary) responses

## Entry Points

**FastAPI app:**
- Location: `backend/app/main.py` (`app = FastAPI(...)`, `default_route_class=AliasRoute`)
- Lifespan: `Base.metadata.create_all` on startup (Alembic preferred in prod), `engine.dispose()` on shutdown
- Launched: `uvicorn app.main:app` (Dockerfile / compose with `--reload` in dev)

**Celery worker:**
- Location: `backend/app/tasks/celery_app.py` (`celery_app`)
- Launched: `celery -A app.tasks.celery_app worker --concurrency=2 -Q celery` (`docker-compose.yml:143`)

**Frontend:**
- Location: `frontend/src/main.tsx` → `App.tsx` (BrowserRouter routes)

## Error Handling

**Strategy:** Centralized exception handlers + structured error envelope.

**Patterns:**
- Global handlers in `main.py:141` (`RequestValidationError` → 400 `VALIDATION_ERROR`) and `main.py:159` (catch-all → 500 `INTERNAL_SERVER_ERROR`), both returning `{success:false, error:{code,message,details}, requestId, disclaimer}`
- Per-route errors via local `_error()` helper raising `HTTPException` with the same envelope (`analysis.py:51`)
- AI pipeline never raises to caller: catches everything and returns `{status:"failed", error}` (`pipeline.py:238`); task layer converts that into a `failed` contract row with mapped `error_code` (`OCR_FAILED` / `ANALYSIS_TIMEOUT` / `INTERNAL_SERVER_ERROR`)
- Celery retry: up to 2 retries with 10s countdown for transient errors only; `ValueError`/`TypeError`/`FileNotFoundError` are not retried (`tasks/analysis.py:281`)

## Cross-Cutting Concerns

**Async isolation (critical pattern):** Each Celery task calls `asyncio.run()` exactly once; all DB updates reuse one `AsyncSession`; the sync AI pipeline runs in a `ThreadPoolExecutor`. Celery sessions use `NullPool` (`database.py:24`) so asyncpg connections are never bound to a stale event loop (avoids "attached to a different loop"). Documented in `tasks/analysis.py:10-15`.

**Logging:** stdlib `logging` at INFO; request correlation via `X-Request-Id` middleware (`main.py:80`) echoed back in response header.

**Validation:** Pydantic v2 schemas (`backend/app/schemas/`); file-type/size checks in the upload handler.

**Authentication:** `get_current_user` dependency decodes JWT (HS256), enforces token `type=="access"`, loads `User` (`core/dependencies.py:18`). Ownership checks (`contract.user_id == current_user.id`) on every analysis resource.

**Rate limiting:** slowapi `Limiter` keyed on remote address (`main.py:36`).

**CORS:** Configurable origins from `CORS_ORIGINS`; exposes `X-Request-Id`, `X-RateLimit-*` headers (`main.py:68`).

---

*Architecture analysis: 2026-06-02*
