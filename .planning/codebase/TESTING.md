# Testing Patterns

**Analysis Date:** 2026-06-02

## Test Framework

**Runner:**
- pytest, configured in `pytest.ini` (project root)
- `addopts = -v --tb=short`, `testpaths = tests`, discovery via `test_*.py` / `Test*` / `test_*`

**Async support:**
- `anyio` is used for async tests, pinned to the asyncio backend. `tests/conftest.py:15` defines an `anyio_backend` fixture parametrized to `["asyncio"]` (trio is not installed). Async tests are marked `@pytest.mark.anyio`.

**Assertion library:**
- Plain `assert` statements (pytest rewriting). No external assertion lib.

**Mocking:**
- `unittest.mock` (`MagicMock`, `AsyncMock`, `patch`) — stdlib only.

**HTTP testing:**
- `httpx.AsyncClient` + `httpx.ASGITransport` against the in-process FastAPI app (no live server).

### Run Commands

```bash
# AI + pure-logic tests (run on host; deps available)
pytest tests/ai                       # AI pipeline / classifier / parser (~132 passing)

# All tests via pytest.ini config (-v --tb=short applied automatically)
pytest

# Backend tests — host usually LACKS FastAPI/SQLAlchemy/httpx deps, so run in docker:
docker compose run --no-deps -w /work -v <repo-root>:/work backend pytest tests/backend
# (~101 backend tests passing in container)
```

Note: backend tests import `app.*` and `httpx`, which are only installed in the `backend` Docker image. The AI tests import `backend.ai.*` and run on the host.

## Test File Organization

**Location:** Centralized under `tests/` (not co-located with source), split by domain:

```
tests/
├── __init__.py
├── conftest.py                     # shared fixtures + sys.path + env isolation
├── ai/                             # AI pipeline tests (host-runnable)
│   ├── test_pipeline.py
│   ├── test_classifier.py
│   ├── test_clause_parser.py
│   └── test_prompts.py
├── backend/                        # FastAPI + service tests (docker-runnable)
│   ├── __init__.py
│   ├── test_api.py                 # endpoint integration tests
│   ├── test_contract_service.py    # pure service-function tests
│   ├── test_analysis_task.py
│   └── test_s3_service.py
└── contracts/                      # test-fixture GENERATORS (not pytest tests)
    ├── make_contracts.py           # builds sample 임대차 PDF files via reportlab
    ├── make_test_contract.py
    └── make_*.py
```

**Naming:** `test_<module>.py`; classes `Test<Feature>`; methods `test_<behavior>`.

**Note on `tests/contracts/`:** these are standalone scripts that GENERATE sample contract PDFs (e.g. `make_contracts.py` writes `계약서_정상형.pdf`, `계약서_위험형.pdf`), not pytest test cases. Run directly: `python tests/contracts/make_contracts.py` (`tests/contracts/make_contracts.py:1`).

## Test Structure

Tests group related cases into `Test*` classes. Example from `tests/ai/test_pipeline.py:133`:

```python
class TestPipelineReturnStructure:
    def test_status_completed(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        assert result["status"] == "completed"

    def test_required_keys_present(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        required = ["contract_id", "status", "error", "raw_text", ...]
        for key in required:
            assert key in result, f"키 누락: {key}"
```

Korean module docstrings list the test scope at the top of each file (`tests/ai/test_pipeline.py:1`, `tests/backend/test_api.py:1`).

## Mocking

### AI pipeline — `run_pipeline_with_text` helper
AI tests never hit S3, OCR, or OpenAI. The helper in `tests/ai/test_pipeline.py:92` writes the contract text to a temp file and patches the three boundary functions:

```python
with patch("backend.ai.pipeline._download_from_s3") as mock_dl, \
     patch("backend.ai.ocr.run_ocr") as mock_ocr, \
     patch("backend.ai.rag.explain_risk") as mock_rag:
    mock_dl.return_value = (contract_text.encode("utf-8"), "text/plain")
    mock_ocr.return_value = {"raw_text": contract_text, "confidence": 1.0, "method": "mock"}
    mock_rag.return_value = {"law_ref": ..., "explanation": ..., ...}
    return run_full_pipeline(contract_id="test-001", s3_key=tmp_path)
```

This exercises the real classifier (rule-based, since no model path) and real clause parser while stubbing external I/O. Error-path tests set `side_effect` (e.g. `mock_dl.side_effect = FileNotFoundError`, `mock_rag.side_effect = RuntimeError`) to assert graceful degradation (`tests/ai/test_pipeline.py:251`, `:273`).

### FastAPI endpoints — `dependency_overrides` + AsyncClient
`tests/backend/test_api.py` overrides auth and DB dependencies and patches service functions:

```python
from app.core.dependencies import get_current_user
from app.core.database import get_db
from app.main import app

app.dependency_overrides[get_current_user] = lambda: mock_user
app.dependency_overrides[get_db] = make_db_override()   # async gen yielding AsyncMock
try:
    with patch("app.services.contract_service.get_contract_by_job_id",
               new_callable=AsyncMock, return_value=mock_contract):
        async with AsyncClient(transport=ASGITransport(app=app),
                               base_url="http://test") as client:
            response = await client.get(f"/api/v1/analysis/{job_id}/status")
finally:
    app.dependency_overrides.clear()   # ALWAYS cleared in finally
```

Key points:
- `dependency_overrides` keys must be the **same function objects** the app imports — tests import `from app.*` (resolved via the `backend/` sys.path entry). Documented at `tests/backend/test_api.py:12`.
- The DB override is an async generator: `make_db_override()` yields `AsyncMock()` (`tests/backend/test_api.py:92`).
- Service-layer functions are patched with `patch("app.services...", new_callable=AsyncMock, return_value=...)` so no real DB/S3 is touched (`tests/backend/test_api.py:164`-`170`).
- Overrides are cleared in a `finally` block every time to prevent leakage between tests.
- Celery dispatch is neutralized: `patch("app.tasks.analysis.run_analysis_task")` then `mock_task.delay = MagicMock()` (`tests/backend/test_api.py:169`).

### MagicMock "contract" objects
DB model instances are simulated with `MagicMock()` whose attributes are set explicitly — `mock_contract` in `tests/backend/test_api.py:42` and the shared `sample_contract_model` / `sample_contract_result` fixtures in `tests/conftest.py:64`, `:123`. These carry realistic `result` dicts (clauses, summary, special_clauses) so response-mapping functions produce valid output.

**What to mock:** S3 (`_download_from_s3`, `upload_contract_file`), OCR (`run_ocr`), RAG/OpenAI (`explain_risk`), Celery (`run_analysis_task.delay`), DB session (`get_db` → `AsyncMock`), auth (`get_current_user`), service queries.

**What NOT to mock:** the rule-based classifier, clause parser, risk-score computation, schema serialization, and the success-wrapper/alias middleware — these are the units under test and run for real.

## Fixtures and Factories

**Shared fixtures** live in `tests/conftest.py`:
- `anyio_backend` — pins async backend to asyncio (`:15`).
- `mock_user` — `MagicMock` authenticated user with fixed UUID `...0001` (`:39`).
- `mock_db` — `AsyncMock` session with `commit`/`rollback`/`close`/`flush` stubbed (`:52`).
- `sample_contract_result` — realistic pipeline-output dict with medium/caution/safe clauses (`:64`).
- `sample_contract_model` — `MagicMock` Contract with stable UUIDs (`id=aaaa...`, `job_id=bbbb...`, `report_id=cccc...`) wrapping `sample_contract_result` (`:123`).

`tests/backend/test_api.py` redefines its own local `mock_user`/`mock_contract` fixtures (slightly different data) rather than reusing conftest — both patterns exist.

**Environment isolation** (`tests/conftest.py:28`-`34`): `os.environ.setdefault(...)` sets test defaults so imports never require real infra:
- `DATABASE_URL=sqlite+aiosqlite:///:memory:` (in-memory SQLite, no Postgres)
- `REDIS_URL` / `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` → localhost stubs
- `SECRET_KEY` → 32-char test key, `APP_ENV=test`

**sys.path setup** (`tests/conftest.py:19`-`26`): both the repo root and `backend/` are prepended to `sys.path`, allowing two import styles seen across tests — `from backend.ai.pipeline import ...` (AI tests, `tests/ai/test_pipeline.py:18`) and `from app.main import app` (backend tests, `tests/backend/test_api.py:25`).

## Coverage

- **No coverage tool configured** (no `pytest-cov`, no coverage thresholds in `pytest.ini`). Coverage is described by passing counts, not percentages: ~132 AI tests, ~101 backend tests reported passing.
- No `--cov` in `addopts`. If coverage is needed, add `pytest-cov` and `--cov=backend`.

## Test Types

**Unit (pure logic):** `tests/backend/test_contract_service.py` imports private functions directly (`_compute_risk_score`, `_compute_risk_level`) and asserts numeric ranges with no mocks needed (`:17`-`60`).

**Integration (in-process API):** `tests/backend/test_api.py` drives the full FastAPI stack — middleware, alias serialization, dependency injection — via `AsyncClient`/`ASGITransport`, asserting status codes and the unwrapped `response.json()["data"]` with camelCase keys (`:183`, `:259`, `:345`).

**Pipeline integration:** `tests/ai/test_pipeline.py` runs `run_full_pipeline` end-to-end with mocked I/O, validating structure, risk classification accuracy, special-clause collection, contract-type detection, and error handling.

**E2E (browser):** None. No Playwright/Cypress configured.

**Frontend unit (Vitest):** `frontend/src/components/*.test.tsx` renders components with Testing Library, asserts DOM output and interaction behavior. Co-located with source, runs in jsdom.

## Common Patterns

**Async test:**
```python
@pytest.mark.anyio
async def test_health_returns_ok(self):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
```
(`tests/backend/test_api.py:102`)

**Error / failure-path test (AI):**
```python
with patch("backend.ai.pipeline._download_from_s3") as mock_dl:
    mock_dl.side_effect = FileNotFoundError("파일 없음")
    result = run_full_pipeline(contract_id="err-001", s3_key="nonexistent/path.pdf")
assert result["status"] == "failed"
assert result["error"] is not None
```
(`tests/ai/test_pipeline.py:251`)

**Error envelope assertion (API):**
```python
assert response.status_code == 400
data = response.json()
assert data["detail"]["error"]["code"] == "FILE_TYPE_INVALID"
```
(`tests/backend/test_api.py:205`)

**Success-wrapper + alias assertion:**
```python
data = response.json()["data"]   # unwrap success envelope
assert data["jobId"] == str(mock_contract.job_id)   # camelCase alias verified
```
(`tests/backend/test_api.py:258`)

---

## Frontend Testing — Vitest + Testing Library

**Updated: 2026-06-07**

**Runner:** Vitest `4.x` with jsdom environment, configured inline in `vite.config.ts` (`test` field).

**Libraries:**
- `@testing-library/react` `16.x` — component rendering and queries
- `@testing-library/jest-dom` `6.x` — DOM matchers (`toBeInTheDocument`, etc.)
- `@testing-library/user-event` `14.x` — realistic user interactions
- `jsdom` `29.x` — browser environment simulation

**Setup file:** `frontend/src/test/setup.ts` — imports `@testing-library/jest-dom` for matcher extensions.

### Run Commands

```bash
# Single run (CI mode)
npm run test                  # vitest run

# Watch mode (development)
npm run test:watch            # vitest

# With coverage
npm run test:coverage         # vitest run --coverage

# Docker (no local Node needed)
docker run --rm -v ./frontend:/app -w /app node:20-alpine sh -c "npx vitest run"
```

### Test File Organization (Frontend)

Tests are co-located with source files:

```
frontend/src/
├── App.test.tsx                       # App mount smoke test
├── components/
│   ├── PrimaryButton.test.tsx         # click, disabled, loading states
│   └── RiskBadge.test.tsx             # risk levels, accessibility
└── test/
    └── setup.ts                       # jest-dom matchers
```

**Naming:** `<ComponentName>.test.tsx` co-located next to the component.

### ESLint

**Config:** `frontend/.eslintrc.cjs` — extends `eslint:recommended`, `@typescript-eslint/recommended`, `react-hooks/recommended`. Plugins: `react-refresh`.

**Run:** `npm run lint` — ESLint with `--max-warnings 5` threshold (minor context-export warnings tolerated).

### Current Coverage

- 3 test files, 11 tests passing
- Components tested: `App`, `PrimaryButton`, `RiskBadge`
- CI integration: `deploy.yml` runs `npm run test` in the `test-frontend` job

---

*Testing analysis updated: 2026-06-07*
