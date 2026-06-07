# External Integrations

**Analysis Date:** 2026-06-02

## APIs & External Services

**LLM / AI:**
- OpenAI GPT-4o — dual use:
  - OCR via Vision API for images and scanned PDFs (`backend/ai/ocr.py`)
  - RAG explanation / legal-grounding generation for risky clauses (`backend/ai/rag.py`)
  - SDK/Client: `openai==1.57.0`
  - Auth: `OPENAI_API_KEY` env var (read inside `backend/ai/`); model name from `OPENAI_MODEL` env (`rag.py:21`)
  - Note: `backend/ai/rag.py:21` default model literal is `gpt-5.4` — verify intended model vs. project's stated GPT-4o.

**Government / Real-estate data:**
- 국토교통부 MOLIT 아파트 실거래가 API (`backend/app/services/market_service.py`)
  - Trade endpoint: `https://apis.data.go.kr/1613000/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade`
  - Rent (전월세) endpoint: `https://apis.data.go.kr/1613000/RTMSDataSvcAptRent/getRTMSDataSvcAptRent`
  - Auth: `MOLIT_API_KEY` (`config.py:36`)
  - Response format: XML (parsed via `xml.etree.ElementTree`); amounts in 만원 → converted to 원
  - Pattern: multi-month parallel aggregation (recent N months) via `httpx`, separated 전세/월세 queries
  - District-code lookup table: `backend/app/data/districts.json`

## Data Storage

**Databases:**
- PostgreSQL 15 (`postgres:15-alpine`, db name `contalktok`)
  - Connection: `DATABASE_URL=postgresql+asyncpg://...` (async driver `asyncpg`)
  - Client: SQLAlchemy 2.0 async (`backend/app/core/database.py`)
  - Pooling: QueuePool for web (`pool_size=10`, `max_overflow=20`); NullPool for Celery tasks (`make_celery_session()`, `database.py:24`)

**Vector DB:**
- ChromaDB (`chromadb/chroma:latest`, host port 8001 → internal 8000)
  - Collection: `lease_law` (`CHROMA_COLLECTION_NAME`)
  - Client: `chromadb==1.5.9` (`backend/ai/rag.py`, `backend/ai/vectordb_builder.py`)
  - Uses a stub embedding function to prevent ONNX auto-download (`rag.py:76` `_StubEmbeddingFunction`)
  - Persisted via `chroma_data` Docker volume

**File Storage:**
- AWS S3 (`S3_BUCKET_NAME`, default `contalktok-contracts`, region `ap-northeast-2`)
  - Client: `boto3` (`backend/app/services/s3_service.py`, `backend/ai/pipeline.py:_s3_download`)
  - Fallback: local filesystem when AWS credentials absent (`LOCAL_UPLOAD_DIR`, default `/tmp/contalktok_uploads`); bind-mounted to `./data/uploads`

**Caching / Broker:**
- Redis 7 (`redis:7-alpine`)
  - Celery broker: `redis://redis:6379/0`
  - Celery result backend: `redis://redis:6379/1`
  - `maxmemory 256mb`, `allkeys-lru` eviction, AOF persistence (`docker-compose.yml`)

## Authentication & Identity

**Auth Provider:** Social OAuth + JWT
- Kakao OAuth (`backend/app/services/auth_service.py:20-21`)
  - Token URL: `https://kauth.kakao.com/oauth/token`; User URL: `https://kapi.kakao.com/v2/user/me`
  - Credentials: `KAKAO_CLIENT_ID` / `KAKAO_CLIENT_SECRET`
  - Endpoint: `POST /api/v1/auth/kakao`
- Google OAuth (`auth_service.py:22-23`)
  - Token URL: `https://oauth2.googleapis.com/token`; User URL: `https://www.googleapis.com/oauth2/v2/userinfo`
  - Credentials: `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`
  - Endpoint: `POST /api/v1/auth/google`
- JWT implementation: `python-jose`, HS256, access + refresh token rotation (`backend/app/core/security.py`)
  - Refresh-token hash stored on `User.refresh_token_hash`
  - Frontend auto-refreshes on `AUTH_TOKEN_EXPIRED` 401 (`frontend/src/api/client.ts:50`)
  - Dev bypass: `POST /api/v1/auth/dev-login`

## Payments

- PortOne / iamport (포트원) (`backend/app/services/payment_service.py`)
  - API base: `https://api.iamport.kr` (token via `/users/getToken`)
  - Credentials: `PORTONE_IMP_KEY` / `PORTONE_IMP_SECRET`; PG provider `PORTONE_PG_PROVIDER` (default `html5_inicis`)
  - Flow: `POST /api/v1/payment/prepare` → `POST /api/v1/payment/verify`; `merchant_uid` format `contalktok_{plan}_{userId}_{ts}`
  - Plans: `single` (5000 KRW), `pass_3month` (19900 KRW)

## Monitoring & Observability

**Error Tracking:** None detected (no Sentry/Datadog SDK in requirements)
**Logs:** Python `logging` (stdlib), `logging.basicConfig(level=INFO)` in `backend/app/main.py`. Request correlation via `X-Request-Id` middleware.

## CI/CD & Deployment

**Hosting:** AWS — EC2 (backend/Docker), RDS PostgreSQL, S3 (contracts + frontend), CloudFront (`infra/terraform/main.tf`)

**CI Pipeline:** GitHub Actions (`.github/workflows/deploy.yml`)
- Triggers: push / PR to `main`
- Job `test-backend`: Python 3.12, postgres + redis service containers, pytest from `backend/`
- Targets ECR repo `contalktok-backend`, ECS task `contalktok-backend-task`, region `ap-northeast-2`

## Environment Configuration

**Required env vars (see `backend/app/core/config.py`):**
`DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `SECRET_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `CHROMA_HOST`, `CHROMA_PORT`, `MOLIT_API_KEY`, `PORTONE_IMP_KEY`, `PORTONE_IMP_SECRET`, `KAKAO_CLIENT_ID/SECRET`, `GOOGLE_CLIENT_ID/SECRET`, `OPENAI_API_KEY`

**Secrets location:** `.env` at repo root (git-ignored; loaded by docker-compose `env_file` and pydantic-settings). A pre-commit hook blocking secret commits was added (commit `7972866`).

## Webhooks & Callbacks

**Incoming:**
- `POST /api/v1/payment/webhook` — PortOne payment webhook (`backend/app/api/v1/payments.py:93`)

**Outgoing:** None detected.

---

*Integration audit: 2026-06-02*
