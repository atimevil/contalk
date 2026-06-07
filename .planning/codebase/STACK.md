# Technology Stack

**Analysis Date:** 2026-06-02

계약똑똑 (contalktok) — AI 임대차 계약서 분석 서비스. 사진/PDF 업로드 → OCR → AI 위험도 분석 → 3단계 리포트.

## Languages

**Primary:**
- Python 3.12 — Backend API, AI pipeline, Celery tasks (`backend/`, declared in `backend/Dockerfile`)
- TypeScript 5.3 — Frontend React app (`frontend/src/`, `frontend/tsconfig.json`)

**Secondary:**
- HCL (Terraform) — AWS infrastructure (`infra/terraform/main.tf`, `variables.tf`)
- SQL / Alembic migrations — schema (`backend/migrations/versions/`)

## Runtime

**Backend Environment:**
- Python 3.12 (`python:3.12-slim` base image, `backend/Dockerfile`)
- Uvicorn (ASGI server) — `uvicorn[standard]==0.32.1`, launched as `uvicorn app.main:app`

**Frontend Environment:**
- Node.js 20 (`node:20-alpine`, `docker-compose.yml` frontend service)
- Vite 5 dev server / build tool

**Package Managers:**
- Backend: pip with `backend/requirements.txt` (runtime) + `backend/requirements-train.txt` (GPU training extras). No lockfile (pinned `==` versions in requirements).
- Frontend: npm with `frontend/package.json`. Lockfile: `frontend/package-lock.json` (committed, pinned deps).

## Frameworks

**Backend Core:**
- FastAPI `0.115.5` — REST API framework (`backend/app/main.py`)
- SQLAlchemy `2.0.36` (async, `[asyncio]` extra) — ORM with async engine
- Pydantic `2.10.3` + pydantic-settings `2.6.1` — schemas, settings, camelCase serialization
- Celery `5.4.0` — async task queue (`backend/app/tasks/celery_app.py`)
- Alembic `1.14.0` — DB migrations

**Frontend Core:**
- React `18.2` + react-dom `18.2`
- react-router-dom `6.21` — client routing (`frontend/src/App.tsx`)
- @tanstack/react-query `5.17` — server state / data fetching
- axios `1.6` — HTTP client (`frontend/src/api/client.ts`)
- TailwindCSS `3.4` + `@tailwindcss/forms` + `@tailwindcss/typography`
- react-dropzone `14.2` — file upload UI

**AI / ML:**
- transformers `>=4.30` + torch `>=2.0` — KLUE-RoBERTa risk classifier inference (`backend/ai/classifier.py`)
- openai `1.57.0` — GPT-4o for OCR Vision + RAG explanation generation (`backend/ai/ocr.py`, `backend/ai/rag.py`)
- chromadb `1.5.9` — vector DB for legal-text RAG retrieval (`backend/ai/rag.py`, `vectordb_builder.py`)
- pdfplumber `0.11.4` — digital PDF text extraction
- pymupdf `1.25.5` (fitz) — scanned-PDF → image conversion for Vision OCR
- Pillow `11.0` — image handling

**Testing:**
- pytest — backend tests (`tests/ai/`, `tests/backend/`, `tests/contracts/`); CI runs `pytest` from `backend/` working dir
- Vitest `4.x` + @testing-library/react `16.x` — frontend component tests (`frontend/src/**/*.test.tsx`); CI runs `npm run test`
- MSW (msw `2.1`) — frontend API mocking (`frontend/src/mocks/`)
- ESLint `8.56` + @typescript-eslint `6.19` — frontend linting (`.eslintrc.cjs` config)

**Build/Dev:**
- Vite `5.0` + `@vitejs/plugin-react` `4.2` — frontend bundling (`frontend/vite.config.ts`)
- ruff — Python linting (`.ruff_cache/` present, version 0.12.0)
- Docker Compose — full local stack (`docker-compose.yml`)

## Key Dependencies

**Critical:**
- `asyncpg==0.30.0` — async PostgreSQL driver (`DATABASE_URL=postgresql+asyncpg://...`)
- `redis==5.2.1` — Celery broker (db 0) and result backend (db 1)
- `boto3==1.35.79` / `botocore` — AWS S3 access (`backend/app/services/s3_service.py`, `backend/ai/pipeline.py`)
- `openai==1.57.0` — both OCR (GPT-4o Vision) and RAG explanation; central to the product
- `chromadb==1.5.9` — RAG legal context retrieval; degrades gracefully to GPT-4o-only fallback when empty

**Auth / Security:**
- `python-jose[cryptography]==3.3.0` — JWT access/refresh tokens (`backend/app/core/security.py`)
- `passlib[bcrypt]==1.7.4` — password hashing
- `slowapi==0.1.9` — rate limiting (`Limiter` in `backend/app/main.py:36`)

**Infrastructure / Utility:**
- `httpx==0.28.0` / `aiohttp==3.11.10` — outbound HTTP (OAuth providers, PortOne, MOLIT API)
- `reportlab==4.2.5` + `PyPDF2==3.0.1` — analysis-result PDF generation (`backend/app/services/pdf_service.py`)
- `python-dateutil==2.9.0` + `pytz` — MOLIT multi-month date calculations

## Configuration

**Environment:**
- Settings via `pydantic-settings` `BaseSettings` (`backend/app/core/config.py`), loaded from `.env` (`extra="ignore"`, `case_sensitive=True`)
- `.env` file present at repo root (referenced by docker-compose `env_file`); contents NOT inspected (secrets)
- Frontend: Vite env vars `VITE_API_URL` / `VITE_API_BASE_URL` / `VITE_ENABLE_MOCK` (`frontend/vite.config.ts`, `frontend/src/api/client.ts`)

**Key configs required (from `config.py`):**
- `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`
- `SECRET_KEY`, `ALGORITHM` (HS256), token expiry settings
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `S3_BUCKET_NAME` (`AWS_REGION` default `ap-northeast-2`)
- `CHROMA_HOST` / `CHROMA_PORT` / `CHROMA_COLLECTION_NAME` (default `lease_law`)
- `MOLIT_API_KEY`, `PORTONE_IMP_KEY` / `PORTONE_IMP_SECRET`, `KAKAO_*`, `GOOGLE_*` OAuth credentials
- `PRICE_SINGLE` (5000 KRW), `PRICE_PASS_3MONTH` (19900 KRW)

**Graceful degradation:** Missing AWS credentials → local filesystem upload mode (`LOCAL_UPLOAD_DIR`); empty ChromaDB → GPT-4o-only RAG; classifier model absent → rule-based keyword fallback.

## Platform Requirements

**Development:**
- Docker + Docker Compose (`docker compose up -d`), then `docker compose exec backend alembic upgrade head`
- Windows + Docker note: Vite uses `usePolling: true` for volume-mount file change detection (`vite.config.ts`)
- HuggingFace model cache persisted via `hf_cache` volume (KLUE-RoBERTa)

**Production:**
- AWS target via Terraform (`infra/terraform/`): VPC + public subnets, EC2 t3.small (backend + Docker), RDS PostgreSQL t3.micro, 2x S3 buckets (contracts + frontend), CloudFront, Security Groups
- CI/CD: GitHub Actions (`.github/workflows/deploy.yml`) — backend pytest job (postgres + redis services), targets ECR repo `contalktok-backend` and ECS task `contalktok-backend-task`

---

*Stack analysis updated: 2026-06-07*
