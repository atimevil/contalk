# Codebase Concerns

**Analysis Date:** 2026-06-02

Severity legend: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low/Informational

Each item below was verified against actual source on 2026-06-02. Refuted claims are marked explicitly.

---

## Tech Debt

**🟢 `OPENAI_MODEL` 기본값이 `.env.example`에 미문서화 + 문서 표기 불일치 (모델명 자체는 정상)**
- 확인: 기본 모델 리터럴은 `gpt-5.4`이며, 이는 프로젝트가 **실제 사용 중인 유효한 OpenAI 모델**이다 (프로젝트 소유자 확인, 2026-06-02). `.env`에도 `OPENAI_MODEL=gpt-5.4`로 명시돼 있어 정상 동작한다. (초기 자동 스캔은 이를 잘못된 모델명으로 오판해 🔴 Critical로 분류했으나, 사실이 아니므로 하향 정정함.)
- Files:
  - `backend/ai/rag.py:21` — `_OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")`
  - `backend/ai/ocr.py:245` — `model = os.environ.get("OPENAI_MODEL", "gpt-5.4")` (동일 기본값, 두 번째 위치)
- 잔여 경미 사항:
  - `OPENAI_MODEL`이 `backend/.env.example`에 없어 신규 배포자가 어떤 모델이 쓰이는지 파악하기 어렵다 (동작엔 문제 없음 — 코드 기본값이 유효).
  - CLAUDE.md/README/일부 docstring이 여전히 "GPT-4o"로 표기 → 실제 사용 모델과 불일치 (문서가 코드보다 오래됨).
- 권고: `backend/.env.example`에 `OPENAI_MODEL=gpt-5.4` 추가, 두 모듈의 중복 env 조회를 단일 공유 상수로 통합, CLAUDE.md 등의 "GPT-4o" 표기 현행화.

**🟡 Open TODO in classifier**
- Issue: Deferred design decision left as an inline TODO.
- File: `backend/ai/classifier.py:9` — `# TODO: "high" 4번째 클래스 추가 여부는 별도 레이블링 작업 완료 후 결정`
- Impact: Risk taxonomy (`high`/`medium`/`caution`/`safe`) may be incomplete; the `high` class depends on a labeling task not yet done. The pipeline already counts `high` in `risk_summary` (`pipeline.py:95`) and treats it as explain-worthy (`_RISK_LEVELS_TO_EXPLAIN`, `pipeline.py:27`), so the classifier and the schema are slightly out of step.
- Fix approach: Resolve the labeling decision, then either fully wire up `high` or remove it consistently.

**🟢 Broad `except Exception` usage (41 occurrences across 11 backend files)**
- Files (counts): `backend/ai/vectordb_builder.py` (9), `backend/app/services/market_service.py` (8), `backend/ai/rag.py` (6), `backend/ai/pipeline.py` (4), `backend/app/api/v1/market.py` (3), `backend/app/tasks/analysis.py` (3), `backend/ai/ocr.py` (2), `backend/ai/classifier.py` (2), `backend/qa_tester.py` (2), `backend/app/core/database.py` (1), `backend/app/services/pdf_service.py` (1).
- Note: Most are deliberate fallback boundaries (OCR → pdfplumber, RAG → degraded response, S3 → local file) and DO log with `exc_info=True`, which is reasonable for a resilience-first pipeline. Flagged as informational, not a defect. The risk is that a real bug (e.g. a config/typo error) could get masked as a routine "service unavailable" fallback rather than surfacing loudly.
- Fix approach: Where a broad except wraps a known fallback, keep it but narrow to the expected exception types where practical; ensure failures that should never happen (config/typo errors) are distinguishable from transient ones.

---

## Known Issues / Bugs

**🟠 Frontend lint is non-functional — `.eslintrc` config MISSING** — VERIFIED
- Issue: `frontend/package.json` defines `"lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0"` and the eslint deps ARE installed (`eslint@^8.56.0`, `@typescript-eslint/*@^6.19.0`, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`), but there is NO eslint config file anywhere (`.eslintrc*` / `eslint.config.*` absent at repo root and in `frontend/`).
- Files: `frontend/package.json` (lint script present); no `frontend/.eslintrc*` exists.
- Impact: `npm run lint` will error out (eslint 8 requires a config). The lint gate is effectively dead — no enforcement of hooks rules, unused vars, etc. Combined with `tsc` in the build step, only type errors are caught, not lint/style issues.
- Fix approach: Add `frontend/.eslintrc.cjs` (or migrate to `eslint.config.js` flat config) wiring up the already-installed plugins, then verify `npm run lint` passes in CI.

**🟡 `make_celery_session` creates a new engine on every call (connection/engine churn)** — VERIFIED
- Issue: `make_celery_session()` calls `create_async_engine(...)` inside the function body on each invocation rather than reusing a module-level engine.
- File: `backend/app/core/database.py:24-42`
- Impact: Each Celery task that builds a session factory instantiates a fresh `AsyncEngine`. `NullPool` correctly avoids cross-event-loop connection reuse (the documented reason), but the engine objects themselves are not disposed, so under sustained task volume this can leak engine resources / file descriptors. Low frequency today (one analysis per upload) but scales poorly.
- Fix approach: Cache one `NullPool` engine per process (module-level) and return fresh sessionmakers from it, or explicitly `await engine.dispose()` after the task completes.

---

## Security Considerations

**🟠 Hardcoded MOLIT API key committed to git history (RESOLVED, but historically present)** — VERIFIED
- History: A MOLIT (국토교통부 / data.go.kr) service key was previously hardcoded in a script. Commit `f06e4fb` ("feat: 국토교통부 실거래가 API 연동 및 계획서 미비사항 수정") was pushed to `origin`, meaning the secret exists in the remote git history.
- Current state (mitigations confirmed):
  - The script (now `scripts/check_molit_rent.py`) reads the key from env: `API_KEY = os.environ.get("MOLIT_API_KEY")` with a guard that exits if unset (`scripts/check_molit_rent.py:16-19`). No literal key remains in the file.
  - A dependency-free pre-commit secret scanner exists at `scripts/git-hooks/pre-commit` and `git config core.hooksPath` is set to `scripts/git-hooks` (verified). It blocks `.env` files, 64-char hex secrets (data.go.kr key shape), `api_key/secret/token/password/serviceKey` literals ≥20 chars, and AWS/OpenAI/GitHub token prefixes.
- Residual risk: The old key still lives in remote history at `f06e4fb`. The user reports the key was rotated, which is the correct remediation. The hook only protects future commits, not the existing history.
- Fix approach (already largely done): Confirm rotation is complete and the old key is revoked at data.go.kr. Optionally scrub history (`git filter-repo`/BFG) if the repo is or will become public; otherwise rotation is sufficient for a private repo. Ensure every contributor runs `git config core.hooksPath scripts/git-hooks` (hooksPath is per-clone, not auto-propagated).

**🟢 `.env` handling is correct**
- `.env` is gitignored (`.gitignore` contains `.env`); `.env.example` and `backend/.env.example` are tracked templates (verified via `git ls-files`). No `.env` file is tracked. No further action needed beyond noting `OPENAI_MODEL` is undocumented (see Tech Debt item 1).

**🟢 OpenAI key partially logged (`sk-...XXXX`)**
- File: `backend/ai/rag.py:241` logs `key=sk-...%s` using only the last 4 chars. This is a standard masked-logging pattern; informational only.

---

## Performance Bottlenecks

**🟡 AI pipeline 60s SLA at risk from serial OCR + parallel GPT fan-out**
- Problem: The documented SLA is "1분 이내" (`pipeline.py:12`). The pipeline explicitly checks and warns when exceeded (`pipeline.py:228-234`).
- Files: `backend/ai/pipeline.py` (S3 download → OCR → parse → classify → RAG fan-out).
- Cause: Steps 1–4 are serial. Step 5 parallelizes RAG/GPT calls with `ThreadPoolExecutor(max_workers=5)` (`pipeline.py:195`), capped to respect OpenAI rate limits. A contract with many `high/medium/caution` clauses + slow Vision OCR + GPT latency can blow the 60s budget; the only handling today is a warning log, not a hard timeout or graceful partial result.
- Improvement path: Add per-clause/overall timeouts, consider streaming/early-return of safe-clause results, and benchmark Vision OCR latency (it is the largest single serial cost). The `max_completion_tokens=4096` per call (`rag.py:253`) with up to 5 concurrent calls is also a latency/cost driver.

**🟡 MOLIT external API dependency, quota, and no retry/backoff**
- Problem: Market pricing depends entirely on the MOLIT (data.go.kr) public API. Calls go through `_call_api` (`market_service.py:183`) with a 15s timeout (`_TIMEOUT = 15.0`, `market_service.py:66`).
- Files: `backend/app/services/market_service.py`, `backend/app/api/v1/market.py`.
- Cause: data.go.kr enforces a daily request quota per service key. The recent change (CLAUDE.md 2026-05-27) made market lookups aggregate "최근 N개월" with parallel collection — multiplying request count per user query by N (1/3/6 months selectable in `ChecklistPage`). There is no retry/backoff, no quota-exhaustion-specific handling, and no caching of MOLIT responses (only the 동 list is cached, `_DONGS_CACHE_TTL = 86400`, `market_service.py:218`).
- Impact: Multi-month aggregation can exhaust the daily quota faster; once exhausted, MOLIT returns an error code which surfaces as `ValueError` (`market_service.py:206-210`) and breaks the feature. A single slow MOLIT response (15s each, N months) also delays the user.
- Improvement path: Cache MOLIT responses (deal data is immutable once published — long TTL safe), add bounded retry/backoff for transient HTTP errors, and add explicit handling/UX for quota-exhaustion (`LIMITED_NUMBER_OF_SERVICE_REQUESTS` family of codes). Monitor daily request volume against the key's quota.

---

## Fragile Areas

**🟠 `_detect_contract_type` heuristic — fragile to OCR quality** — VERIFIED (residual risk remains)
- Files: `backend/ai/pipeline.py:357-387` (`_detect_contract_type`), `backend/ai/pipeline.py:334-354` (`_extract_amount_near`), regex `_AMOUNT_RE` at `pipeline.py:331`.
- Why fragile: Contract type (jeonse/monthly) is inferred from OCR text via keyword + amount heuristics. The recent improvement (amount-based: month-rent keyword followed by a non-zero amount → `monthly`) is a genuine upgrade over naive keyword matching and includes a clever guard skipping amounts preceded by "보증금"/"전세" within a 20-char window. But it is still inherently dependent on OCR fidelity:
  - The amount regex requires a unit suffix `만원`/`원` immediately after the number; OCR errors that drop or garble the unit, insert spaces beyond the 20-char window, or misread digits will cause misdetection.
  - Standard contract forms print the label "차임(월세)" even on jeonse contracts; detection relies on there being no real amount near it — true for clean OCR, brittle for noisy scans.
  - Misclassification cascades: contract_type drives which market comparison (jeonse 전세가율 vs monthly 월세 시세) the user is shown.
- Residual risk: Even after the amount-based improvement, a low-quality photo/scan (the primary input modality) can yield `unknown` or a wrong type. There is no confidence score on the detection and no user override path (the manual selection UI was intentionally removed per CLAUDE.md 2026-05-27).
- Safe modification: Add a detection-confidence signal and surface a "유형이 확실하지 않습니다" affordance for low-confidence cases; consider re-introducing an optional user override for `unknown`. Add fixtures with deliberately degraded OCR text to the test suite.

**🟡 Clause parsing fallback collapses entire document into one clause**
- File: `backend/ai/pipeline.py:139-141` — if `parse_clauses` returns nothing, the whole `raw_text[:2000]` becomes a single "전문" clause.
- Why fragile: On parsing failure (unusual contract layout / poor OCR), the analysis silently degrades to one truncated clause, losing per-clause risk granularity without flagging it prominently to the user.
- Safe modification: Surface a "조항 자동 분리 실패" warning in the result so downstream UI can inform the user.

---

## Workflow / Process Concerns

**🟡 Active development directly on `master` (no feature-branch workflow)** — VERIFIED
- Issue: `git branch --show-current` → `master`. Recent commits (per git log) and current uncommitted working changes (`backend/ai/pipeline.py`, several `frontend/src/*`, `tests/ai/test_pipeline.py`) are all on `master`.
- Impact: Diverges from the project's own RULES guidance ("Feature Branches Only ... never work on main/master"). No PR review gate, harder rollback, riskier history.
- Fix approach: Adopt `feature/*` branches + PR review for non-trivial changes; reserve direct `master` commits for docs/trivial fixes.

**🟡 Test execution requires Docker; no host-native test path documented**
- Backend: Test dependencies are not installed on the host — backend tests are intended to run inside Docker (`docker-compose.yml` present). `tests/conftest.py` does configure an in-memory async SQLite DB (`sqlite+aiosqlite:///:memory:`, `conftest.py:29`), so the test harness itself is sound; the gap is environment provisioning, not test design.
- Frontend: Build/`dist` is produced only via Docker or local `npm` (`build: "tsc && vite build"`), and there is NO frontend test framework at all (no vitest/jest in `frontend/package.json` deps).
- Impact: Quick local verification is friction-heavy; the frontend has zero automated test coverage and (per the lint item above) a dead lint gate — so the entire frontend quality gate is currently manual.
- Fix approach: Document a host-native `pip install -r` path for backend tests; add a frontend test runner (vitest integrates cleanly with Vite) and at minimum smoke-test the API client and key pages; fix eslint config so lint runs.

---

## Repository Hygiene (Informational)

**🟢 Large AIHub legal datasets present on disk but correctly gitignored**
- Directories: `019.법률, 규정 (판결서, 약관 등) 텍스트 분석 데이터/` (measured ~423MB), `05.계약 법률 문서 서식 데이터/`, plus `data/`, `models/` (contains `roberta_risk_classifier`), `chroma_data/`.
- Status: All are listed in `.gitignore` and NONE are tracked (`git ls-files` returns 0 dataset files). These are training/reference data and model artifacts, not application code.
- Note: No concern for the repo, but contributors must obtain these out-of-band; the AIHub data and `models/roberta_risk_classifier` are prerequisites for the classifier and `vectordb_builder.py` to function. Document the provisioning steps if not already covered.

---

## Test Coverage Gaps

**🟠 Frontend: zero automated test coverage**
- What's not tested: All of `frontend/src/` — pages, API client (`frontend/src/api/market.ts`), upload flow, result rendering. No test framework installed.
- Risk: UI/regression bugs ship unguarded; only `tsc` type-checking applies.
- Priority: High (frontend is the entire user-facing surface).

**🟡 AI pipeline: contract-type detection lacks degraded-OCR fixtures**
- What's not tested: `_detect_contract_type` against noisy/garbled OCR text (the realistic input). `tests/ai/test_pipeline.py` exists and has uncommitted changes, but the heuristic's failure modes (missing units, mislabeled forms) need explicit negative fixtures.
- Files: `backend/ai/pipeline.py:357-387`, `tests/ai/test_pipeline.py`.
- Risk: Misclassification silently shows wrong market comparison to users.
- Priority: Medium.

---

*Concerns audit: 2026-06-02*
