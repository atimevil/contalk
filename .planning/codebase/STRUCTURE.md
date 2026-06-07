# Codebase Structure

**Analysis Date:** 2026-06-02

## Directory Layout

```
make/
├── backend/
│   ├── app/
│   │   ├── api/v1/           # FastAPI routers (auth, analysis, payments, market)
│   │   ├── services/         # Business logic + external integrations
│   │   ├── models/           # SQLAlchemy ORM entities
│   │   ├── schemas/          # Pydantic request/response models (CamelModel)
│   │   ├── tasks/            # Celery app + analysis task
│   │   ├── core/             # config, database, security, dependencies
│   │   ├── data/             # districts.json (MOLIT region codes)
│   │   └── main.py           # FastAPI entry point (AliasRoute, middleware)
│   ├── ai/                   # Self-contained AI pipeline (no app.* imports)
│   ├── migrations/           # Alembic migrations (env.py + versions/)
│   ├── requirements.txt      # Runtime deps
│   ├── requirements-train.txt# GPU training extras
│   ├── Dockerfile            # python:3.12-slim
│   └── qa_tester.py          # Ad-hoc QA script
├── frontend/
│   ├── src/
│   │   ├── pages/            # Route-level screens
│   │   ├── components/       # Reusable UI components + *.test.tsx
│   │   ├── api/              # axios clients per domain
│   │   ├── context/          # AuthContext, ToastContext
│   │   ├── types/            # TS API types (api.ts)
│   │   ├── mocks/            # MSW handlers
│   │   ├── test/             # Vitest setup (setup.ts)
│   │   ├── App.tsx           # Router
│   │   ├── App.test.tsx      # App smoke test
│   │   └── main.tsx          # React entry
│   ├── .eslintrc.cjs         # ESLint config (TS + React)
│   ├── package.json
│   ├── package-lock.json     # npm lockfile (pinned deps)
│   ├── vite.config.ts        # proxy + usePolling + vitest config
│   └── tsconfig.json         # path alias @/* → src/*
├── tests/                    # pytest (ai/, backend/, contracts/)
├── infra/terraform/          # AWS IaC (main.tf, variables.tf)
├── docs/                     # API_FINAL.md, CHANGES_FROM_INITIAL.md
├── .github/workflows/        # deploy.yml (CI/CD)
├── docker-compose.yml        # Full local stack (6 services)
└── CLAUDE.md                 # Project harness / change log
```

Note: two large Korean AIHub legal-text dataset directories (`019.법률...`, `05.계약...`) sit at repo root — these are training-data sources, not application code.

## Directory Purposes

**`backend/app/api/v1/`:**
- Purpose: HTTP endpoint definitions
- Key files: `analysis.py` (upload/status/result/pdf/special-clauses/history/quota), `auth.py` (kakao/google/refresh/agree/logout/me/dev-login), `payments.py` (prepare/verify/history/webhook), `market.py` (real-estate price queries)
- Convention: `auth`/`market`/`payment` routers declare their own `prefix`; `analysis` router has none (full paths in decorators)

**`backend/app/services/`:**
- Purpose: business logic; one module per domain
- Key files: `contract_service.py`, `auth_service.py` (OAuth + JWT), `payment_service.py` (PortOne), `market_service.py` (MOLIT XML), `s3_service.py` (S3 + local fallback), `pdf_service.py` (reportlab)

**`backend/app/models/`:**
- Purpose: ORM entities; all inherit `Base` from `core/database.py`
- Key files: `user.py`, `contract.py` (status/progress/result JSONB), `payment.py`, `quota.py`, `special_clause.py`

**`backend/app/schemas/`:**
- Purpose: Pydantic models; inherit `CamelModel` (`common.py`)
- Key files: `common.py` (CamelModel, SuccessResponse, ErrorResponse, DISCLAIMER), `analysis.py`, `auth.py`, `payment.py`, `market.py`, `special_clause.py`

**`backend/ai/`:**
- Purpose: AI pipeline, isolated from web layer
- Key files: `pipeline.py` (entry `run_full_pipeline`), `ocr.py` (GPT-4o Vision + pdfplumber), `clause_parser.py`, `classifier.py` (KLUE-RoBERTa + rule fallback), `rag.py` (ChromaDB + GPT-4o), `prompts.py`, `vectordb_builder.py` (index legal corpus), `train.py` (classifier training), `data_prep.py`

**`frontend/src/pages/`:**
- Purpose: one component per route (see `App.tsx`)
- Key files: `HomePage`, `UploadPage`, `AnalyzingPage` (polling), `ResultPage`, `SpecialClausesPage`, `ChecklistPage`, `PaymentPage`, `LoginPage`, `MyPage`, `ErrorPage`

**`frontend/src/api/`:**
- Purpose: typed axios wrappers per domain
- Key files: `client.ts` (axios instance, interceptors, token refresh), `analysis.ts`, `auth.ts`, `market.ts`, `payment.ts`, `specialClauses.ts`

## Key File Locations

**Entry Points:**
- `backend/app/main.py`: FastAPI app, middleware, exception handlers, router mounting
- `backend/app/tasks/celery_app.py`: Celery app instance
- `frontend/src/main.tsx` → `frontend/src/App.tsx`: React app + routes

**Configuration:**
- `backend/app/core/config.py`: pydantic-settings `Settings`
- `frontend/vite.config.ts`: dev server proxy, polling
- `docker-compose.yml`: service topology
- `infra/terraform/main.tf`: AWS resources

**Core Logic:**
- `backend/ai/pipeline.py`: analysis orchestration
- `backend/app/tasks/analysis.py`: Celery ↔ pipeline ↔ DB glue (async-isolation pattern)
- `backend/app/services/`: per-domain business logic

**Testing:**
- `tests/ai/` (e.g. `test_pipeline.py`), `tests/backend/`, `tests/contracts/`

## Naming Conventions

**Backend (Python):**
- Files: `snake_case.py` (`market_service.py`, `clause_parser.py`)
- Functions/vars: `snake_case`; private helpers prefixed `_` (`_download_from_s3`, `_run_rag`)
- Classes: `PascalCase` (`Contract`, `CamelModel`, `AliasRoute`)
- Services: `<domain>_service.py` exposing module-level async functions (not classes)

**Frontend (TypeScript):**
- Component files & components: `PascalCase.tsx` (`UploadZone.tsx`, `ResultPage.tsx`)
- API modules: `camelCase.ts` (`specialClauses.ts`)
- Path alias: `@/*` → `src/*` (`tsconfig.json`)

**API JSON:** camelCase on the wire (enforced by `CamelModel` + `AliasRoute`), snake_case internally.

## Where to Add New Code

**New API endpoint:**
- Add handler to the relevant router in `backend/app/api/v1/<domain>.py` (or a new router mounted in `main.py:182`)
- Put business logic in `backend/app/services/<domain>_service.py`
- Define request/response in `backend/app/schemas/<domain>.py` extending `CamelModel`
- Response auto-wrapping + camelCasing are automatic — return the Pydantic model directly

**New AI pipeline step:**
- Add a module under `backend/ai/` and wire it into `run_full_pipeline()` (`pipeline.py`)
- Keep it dependency-clean: do NOT import `app.*` from `backend/ai/`

**New async/background job:**
- Add a `@celery_app.task` in `backend/app/tasks/`
- Follow the async-isolation pattern: single `asyncio.run()`, one `AsyncSession` via `make_celery_session()`, sync work in a thread pool (mirror `tasks/analysis.py`)

**New DB model / column:**
- Add/modify entity in `backend/app/models/`, then create an Alembic migration in `backend/migrations/versions/`

**New frontend screen:**
- Add `frontend/src/pages/<Name>Page.tsx`, register a `<Route>` in `App.tsx`
- Add an API wrapper in `frontend/src/api/` using the shared `apiClient`
- Add/extend TS types in `frontend/src/types/api.ts`

**New reusable UI:**
- `frontend/src/components/<Name>.tsx` (PascalCase)

## Special Directories

**`backend/app/data/`:**
- Purpose: `districts.json` (MOLIT 법정동 codes for market queries)
- Generated: No · Committed: Yes

**`frontend/src/mocks/`:**
- Purpose: MSW handlers; activated when `VITE_ENABLE_MOCK=true`
- Generated: No · Committed: Yes

**`019.법률...` / `05.계약...` (repo root):**
- Purpose: AIHub training/validation datasets for the classifier
- Generated: No (external dataset) · Committed: present in tree (large — likely should be excluded from app builds)

**`hf_cache` / `chroma_data` (Docker volumes):**
- Purpose: KLUE-RoBERTa model cache and ChromaDB persistence
- Generated: Yes · Committed: No (named volumes)

---

*Structure analysis updated: 2026-06-07*
