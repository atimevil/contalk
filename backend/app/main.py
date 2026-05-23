"""
계약똑똑 FastAPI Application Entry Point
"""
import uuid
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded


class AliasRoute(APIRoute):
    """
    모든 response_model을 alias(camelCase)로 직렬화하는 커스텀 라우트 클래스.
    CamelModel의 alias_generator=to_camel 설정과 연동된다.
    """
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("response_model_by_alias", True)
        super().__init__(*args, **kwargs)

from app.core.config import settings
from app.core.database import engine, Base
from app.schemas.common import DISCLAIMER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup/shutdown lifecycle."""
    logger.info("Starting up 계약똑똑 API v%s [%s]", settings.APP_VERSION, settings.APP_ENV)
    # Create tables (use Alembic migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized.")
    yield
    logger.info("Shutting down.")
    await engine.dispose()


app = FastAPI(
    title="계약똑똑 API",
    description="임대차 계약서 AI 분석 서비스",
    version=settings.APP_VERSION,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
    # BUG-001 fix: 모든 라우트의 response_model을 camelCase alias로 직렬화
    default_route_class=AliasRoute,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
)


# ─── Request ID middleware ────────────────────────────────────────────────────

@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


# ─── Global exception handlers ───────────────────────────────────────────────

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "요청 데이터가 유효하지 않습니다.",
                "details": exc.errors() if not settings.is_production else None,
            },
            "requestId": request_id,
            "disclaimer": DISCLAIMER,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error("Unhandled exception [%s]: %s", request_id, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "서버 내부 오류가 발생했습니다.",
                "details": str(exc) if not settings.is_production else None,
            },
            "requestId": request_id,
            "disclaimer": DISCLAIMER,
        },
    )


# ─── Routes ──────────────────────────────────────────────────────────────────

from app.api.v1 import auth, analysis, payments, market

app.include_router(auth.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(market.router, prefix="/api/v1")


# ─── Health check ────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
    }


@app.get("/api/v1/health", tags=["health"])
async def api_health_check():
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
    }
