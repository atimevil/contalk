# Coding Conventions

**Analysis Date:** 2026-06-02

This codebase has two distinct convention domains: **Backend (Python / FastAPI)** under `backend/app/` and `backend/ai/`, and **Frontend (TypeScript / React)** under `frontend/src/`. Conventions differ between them and are documented separately below.

---

## Backend (Python)

### Naming Patterns

**Files:**
- snake_case modules: `contract_service.py`, `market_service.py`, `clause_parser.py`
- Layered by responsibility: `api/v1/<domain>.py`, `services/<domain>_service.py`, `schemas/<domain>.py`, `models/<domain>.py`, `ai/<step>.py`

**Functions:**
- snake_case: `get_current_user`, `run_full_pipeline`, `_compute_risk_score`
- Public service functions are plain verbs: `create_contract`, `check_and_consume_quota`
- Leading underscore for module-private helpers: `_error`, `_detect_contract_type`, `_extract_amount_near`, `_validate_district_code` (e.g. `backend/app/api/v1/market.py:44`, `backend/ai/pipeline.py:334`)

**Variables / Constants:**
- snake_case for variables, UPPER_SNAKE for module constants: `ALLOWED_CONTENT_TYPES`, `MAX_FILE_SIZE_BYTES` (`backend/app/api/v1/analysis.py:47`), `MARKET_QUERY_LIMIT` (`backend/app/api/v1/market.py:41`)
- Private module constants also prefixed with `_`: `_RISK_LEVELS_TO_EXPLAIN`, `_DISCLAIMER`, `_AMOUNT_RE`, `_RISK_RULES` (`backend/ai/pipeline.py`, `backend/ai/classifier.py`)

**Types / Classes:**
- PascalCase: `CamelModel`, `AliasRoute`, `SuccessResponse`, `AptTradeStat`
- Pydantic schema classes live in `backend/app/schemas/`

### Response Convention (CRITICAL)

The backend enforces a uniform success envelope via middleware in `backend/app/main.py:95` (`wrap_success_response`):

```python
# All 2xx application/json responses are auto-wrapped:
{"success": True, "data": <original_body>, "disclaimer": DISCLAIMER}
```

Rules to follow when writing endpoints:
- **Return the bare `response_model` object** — the middleware wraps it. Do NOT manually wrap in `{success, data}` unless you need custom `meta` (see below).
- Responses already containing a `success` key are **not** re-wrapped (`backend/app/main.py:127`).
- Excluded from wrapping: `/health`, `/docs`, `/redoc`, `/openapi`, `/api/v1/health`, and any path ending in `/pdf` (`backend/app/main.py:93`, `:107`).
- When you need pagination `meta`, return the full dict manually (the middleware sees the `success` key and passes it through). Example: `get_analysis_history` in `backend/app/api/v1/analysis.py:380` returns `{"success": True, "data": {...}, "meta": {...}, "disclaimer": DISC}`.
- `DISCLAIMER` constant is defined in `backend/app/schemas/common.py:7` and duplicated in `backend/app/core/dependencies.py:15` and `backend/ai/pipeline.py:30`.

### camelCase Serialization Convention (CRITICAL)

Schemas serialize snake_case Python fields to camelCase JSON for the TS frontend:

- All response schemas inherit from `CamelModel` (`backend/app/schemas/common.py:10`), which sets `alias_generator=to_camel`, `populate_by_name=True`, `from_attributes=True`.
- The global `default_route_class=AliasRoute` (`backend/app/main.py:60`, defined `:20`) forces `response_model_by_alias=True` on every route, so `report_id` → `reportId`, `job_id` → `jobId`.
- `populate_by_name=True` means internal code can still construct schemas with snake_case kwargs.

**Intentional divergence — `backend/app/schemas/market.py`:**
- Market schemas (`AptTradeStat`, `AptRentStat`, `DistrictItem`, etc.) inherit from plain `pydantic.BaseModel`, **NOT** `CamelModel`. Fields stay snake_case in JSON (`price_krw`, `avg_deposit_krw`, `district_code`).
- The matching TS types in `frontend/src/types/api.ts:286` use snake_case (`avg_price_krw`, `monthly_rent_krw`) to align.
- `SidoItem.districts` uses an explicit Korean alias `"시군구"` with `model_config = {"populate_by_name": True}` (`backend/app/schemas/market.py:23`). The frontend type mirrors this with a `시군구` field (`frontend/src/types/api.ts:273`).
- **Rule:** new market endpoints stay snake_case (BaseModel); everything else uses `CamelModel`.

### Error Handling

Two error envelope styles coexist:

1. **Global handlers** (`backend/app/main.py:141`, `:159`) — produce `success: false` with `error.{code,message,details}`, `requestId`, `disclaimer`. Used for `RequestValidationError` (code `VALIDATION_ERROR`, 400) and uncaught `Exception` (code `INTERNAL_SERVER_ERROR`, 500). `details` is suppressed in production (`settings.is_production`).

2. **Per-route `HTTPException`** — the `detail` payload carries the error envelope. Two helper patterns exist:
   - `_error(code, message, status_code, request_id)` in `backend/app/api/v1/analysis.py:51` raises `HTTPException(detail={"success": False, "error": {code, message}, "request_id", "disclaimer"})`.
   - Market endpoints raise `HTTPException(detail={"error": {code, message}, "disclaimer"})` inline (`backend/app/api/v1/market.py:48`, `:172`).
   - Auth dependency raises `HTTPException(detail={"success": False, "error": {code, message}})` (`backend/app/core/dependencies.py:22`).

**Error codes** are a fixed vocabulary. The frontend mirrors them as a `ErrorCode` union in `frontend/src/types/api.ts:29` (e.g. `AUTH_TOKEN_EXPIRED`, `FILE_TYPE_INVALID`, `QUOTA_EXCEEDED`, `ANALYSIS_NOT_FOUND`, `VALIDATION_ERROR`, `FORBIDDEN`, `INTERNAL_SERVER_ERROR`). Backend-only codes seen in routes but not yet in the union: `MOLIT_API_KEY_NOT_SET`, `MOLIT_API_ERROR`, `MARKET_SERVICE_UNAVAILABLE`, `MARKET_QUOTA_EXCEEDED`. Keep both lists in sync when adding codes.

**Defensive parsing with fallbacks** is pervasive:
- Resource lookups follow `parse UUID → 404 on ValueError → fetch → 404 if None → 403 if not owner` (`backend/app/api/v1/analysis.py:122`-`141`). Replicate this guard sequence in new ownership-scoped endpoints.
- Dict access uses `.get(key, default)` with prioritized fallbacks. Example special-clause text resolution: AI draft → pipeline `special_texts` → `recommendation` → original-text slice (`backend/app/api/v1/analysis.py:239`-`245`).
- `getattr(settings, "MOLIT_API_KEY", "")` guards optional config (`backend/app/api/v1/market.py:46`).
- `_default_deal_ym()` falls back to manual month math if `dateutil` is missing (`backend/app/api/v1/market.py:91`).

### Comments & Docstrings

- **Korean docstrings and comments throughout.** Module docstrings list the endpoints and behavior (`backend/app/api/v1/market.py:1`, `backend/ai/pipeline.py:1`).
- Function docstrings use Korean prose, often with NumPy-style `Parameters` / `Returns` sections for AI functions (`backend/ai/pipeline.py:37`).
- Inline section dividers use box-drawing rules: `# ─── Section ───` and `# ---` (`backend/app/main.py:78`, `backend/ai/pipeline.py:33`).
- Bug-fix and behavior rationale recorded inline with tags like `BUG-001 fix:` (`backend/app/main.py:59`) and `# TODO:` for deferred work (`backend/ai/classifier.py:9`).

### Async & Concurrency

- API route handlers are `async def`; DB sessions injected via `db: AsyncSession = Depends(get_db)`.
- Blocking/synchronous service calls (MOLIT HTTP, market service) are offloaded with `await asyncio.to_thread(...)` (`backend/app/api/v1/market.py:167`, `:311`).
- `await db.commit()` / `await db.flush()` are explicit in routes after mutations (`backend/app/api/v1/analysis.py:104`, `:370`).

### Imports

- Standard library → third-party → local app, grouped (`backend/app/api/v1/analysis.py:14`-`43`).
- `from __future__ import annotations` at top of newer modules (`backend/ai/pipeline.py:16`, `backend/app/schemas/market.py:8`, `backend/app/api/v1/market.py:16`).
- **Function-internal (deferred) imports** are a deliberate pattern to avoid heavy import cost and circular deps:
  - Route handlers import Celery task at call time: `from app.tasks.analysis import run_analysis_task` (`backend/app/api/v1/analysis.py:107`); PDF service inside handler (`:185`, `:310`).
  - AI pipeline imports each step inside `run_full_pipeline` so optional heavy deps (OCR, transformers, boto3) only load when reached: `from .ocr import run_ocr` (`backend/ai/pipeline.py:109`), `from .classifier import classify_risk` (`:145`), `from .rag import explain_risk` (`:152`), `import boto3` (`:272`), `from transformers import ...` (`backend/ai/classifier.py:172`).

---

## AI Pipeline (`backend/ai/`)

### Function-Internal Imports
As above — every external/heavy dependency is imported inside the function that uses it, wrapped in `try/except ImportError` with a logged fallback (`backend/ai/classifier.py:198`, `backend/ai/pipeline.py:291`).

### Rule-Based Fallbacks
- The classifier is a hybrid: it tries the fine-tuned KLUE-RoBERTa model and falls back to regex rules when the model is absent or fails (`backend/ai/classifier.py:113`, `:154`, `:306`).
- Model loading is a one-shot singleton guarded by `_MODEL_CACHE` / `_MODEL_LOAD_ATTEMPTED` (`backend/ai/classifier.py:150`-`203`). If `KLUE_ROBERTA_MODEL_PATH` is unset, returns `None` and logs an info-level message (rule-based mode).
- Risk rules are an ordered list of `(compiled_regex, risk_level)` tuples evaluated top-down (`backend/ai/classifier.py:27`). Add new patterns in priority order.
- Hybrid override logic (rule-medium wins, safe-override patterns, downgrade-to-caution) is documented inline at `backend/ai/classifier.py:228`-`299`.
- S3 download falls back to local file read when AWS creds are absent (`backend/ai/pipeline.py:251`-`306`) — supports local/test runs.

### Parallel Processing
- RAG/GPT-4o explanations run in a `ThreadPoolExecutor(max_workers=5)` over only the risk-bearing clauses; `as_completed` collects results and original order is restored via an index map (`backend/ai/pipeline.py:153`, `:194`-`210`). `max_workers=5` is chosen as an OpenAI rate-limit safety margin.
- Each parallel task wraps its work in `try/except` and returns a graceful degraded clause on failure (`backend/ai/pipeline.py:173`-`192`) — a single RAG failure never crashes the pipeline.

### Result Contract
- `run_full_pipeline()` always returns a dict with a stable key set (documented at `backend/ai/pipeline.py:50`-`81`); on any exception it returns `status="failed"` with `error` populated rather than raising (`backend/ai/pipeline.py:238`).
- SLA target is 60s; the pipeline logs a warning if exceeded (`backend/ai/pipeline.py:228`).
- Every module has an `if __name__ == "__main__":` standalone test block for manual runs (`backend/ai/pipeline.py:414`, `backend/ai/classifier.py:326`).

---

## Frontend (TypeScript / React)

### Naming Patterns

**Files:**
- Components: PascalCase `.tsx` — `ClauseCard.tsx`, `RiskBadge.tsx`, `PrimaryButton.tsx` (`frontend/src/components/`)
- Pages: PascalCase `*Page.tsx` — `ChecklistPage.tsx`, `ResultPage.tsx`, `UploadPage.tsx` (`frontend/src/pages/`)
- API layer: camelCase `.ts` — `client.ts`, `analysis.ts`, `market.ts`, `auth.ts` (`frontend/src/api/`)
- Types: `frontend/src/types/api.ts`
- Context: PascalCase `*Context.tsx` (`frontend/src/context/`)

**Functions / Variables:** camelCase (`generateId`, `subscribeTokenRefresh`, `handleToggle`).

**Types / Interfaces:** PascalCase interfaces (`AnalysisClause`, `MarketSummaryResponse`); union string literal types for enums (`AnalysisStatus`, `RiskLevel`, `ErrorCode` in `frontend/src/types/api.ts`).

### apiClient (axios)
Single shared instance in `frontend/src/api/client.ts`:
- `baseURL` from `import.meta.env.VITE_API_BASE_URL` defaulting to `/api/v1` (`client.ts:3`).
- **Request interceptor** injects `Authorization: Bearer <accessToken>` from `localStorage` and an `X-Request-Id` (`client.ts:20`-`30`).
- **Response interceptor** handles `401` + `AUTH_TOKEN_EXPIRED`: refreshes the token via `POST /auth/refresh`, queues concurrent requests with `subscribeTokenRefresh`/`onRefreshed`, and retries the original request once (`_retry` flag) (`client.ts:45`-`93`).
- On refresh failure it clears tokens and dispatches a `window` `CustomEvent('auth:logout')` rather than a hard redirect, so `AuthContext` can navigate via React Router (`client.ts:78`-`84`).

### API Layer Pattern
Each domain exports an object of async methods that call `apiClient` and **unwrap the success envelope**:
- Standard unwrap returns `res.data.data` (`frontend/src/api/analysis.ts:19`, `frontend/src/api/auth.ts:16`). Response generics are typed as `{ success: true; data: T }`.
- Paginated calls also read `res.data.meta` (`frontend/src/api/analysis.ts:48`-`58`).
- Binary downloads use `responseType: 'blob'` and return `res.data` directly (`frontend/src/api/analysis.ts:36`).
- `market.ts` uses a defensive `unwrap<T>()` helper that returns `body.data` if present, else `body` — tolerating both wrapped and raw responses (`frontend/src/api/market.ts:12`-`18`). Use this pattern when an endpoint may not be wrapped.
- Non-2xx responses throw `AxiosError`; callers branch on `err.response?.status` (documented at `frontend/src/api/market.ts:60`-`64`).

### Component Style
- **Functional components with hooks** only; default export per file (`frontend/src/components/ClauseCard.tsx:11`).
- Props typed via a local `interface <Name>Props` with defaults destructured in the signature (`ClauseCard.tsx:5`-`11`).
- Local state via `useState`; optional callbacks invoked with optional chaining `onExpand?.(clause.id)` (`ClauseCard.tsx:16`).
- `import type { ... }` for type-only imports (`ClauseCard.tsx:3`).

### Styling — TailwindCSS
- Utility classes inline in `className`; config in `frontend/tailwind.config.js` with `@tailwindcss/forms` and `@tailwindcss/typography` plugins (`frontend/package.json:24`).
- Conditional styling via lookup maps keyed by domain enums, e.g. `borderColorMap[clause.risk]` (`ClauseCard.tsx:19`-`24`). Custom classes like `shadow-card`, `animate-fade-in` come from the Tailwind config.
- Korean UI copy and emoji prefixes in labels (e.g. `💬 쉬운 설명`, `📝 권고사항`).

### Comments
- Korean inline comments explaining intent and bug-fix references (e.g. `// BUG-005 fix:` in `frontend/src/types/api.ts:61`; rationale comments in `client.ts:81`).

### Imports
- React / external first, then local API/types/components. Type imports separated with `import type`.

---

## Cross-Cutting

| Concern | Backend | Frontend |
|---------|---------|----------|
| Response shape | `{success, data, disclaimer}` enforced by middleware (`backend/app/main.py:95`) | `res.data.data` unwrap in API layer (`frontend/src/api/*.ts`) |
| Field casing | camelCase via `CamelModel`; market = snake_case `BaseModel` | camelCase TS interfaces; market types snake_case to match |
| Error codes | `error.code` string vocabulary | `ErrorCode` union (`frontend/src/types/api.ts:29`) |
| Auth | `get_current_user` Bearer dependency (`backend/app/core/dependencies.py:18`) | Bearer interceptor + 401 refresh (`frontend/src/api/client.ts`) |
| Language | Korean docstrings/comments | Korean comments + UI copy |

---

*Convention analysis: 2026-06-02*
