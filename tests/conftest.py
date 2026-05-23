"""
공유 pytest 픽스처 및 설정.

모든 테스트에서 공통으로 사용하는 픽스처를 정의한다.
"""
import sys
import os
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock


# anyio 백엔드를 asyncio로 고정 (trio 미설치)
@pytest.fixture(params=["asyncio"])
def anyio_backend(request):
    return request.param

# ─── sys.path 설정 ─────────────────────────────────────────────────────────────
# 프로젝트 루트(make/)를 추가 — 'backend' 패키지를 최상위에서 import 하기 위해
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT, "backend")
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# ─── 환경변수 기본값 (테스트 격리) ───────────────────────────────────────────
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-characters-long")
os.environ.setdefault("APP_ENV", "test")


# ─── 유저 모의 픽스처 ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_user():
    """인증된 사용자 모의 오브젝트."""
    user = MagicMock()
    user.id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user.email = "test@example.com"
    user.nickname = "테스트유저"
    user.provider = "kakao"
    user.terms_agreed = True
    user.privacy_agreed = True
    return user


@pytest.fixture
def mock_db():
    """비동기 SQLAlchemy 세션 모의 오브젝트."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.close = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def sample_contract_result():
    """파이프라인 → DB 변환 완료된 샘플 result dict."""
    return {
        "contract_id": "test-contract-001",
        "clauses": [
            {
                "id": str(uuid.uuid4()),
                "risk": "medium",
                "clause_number": "제4조",
                "original_text": "수선 책임은 소모성 부품을 포함하여 임차인이 전부 부담한다.",
                "explanation": "임차인에게 불리한 조항입니다.",
                "law_reference": {
                    "law_name": "주택임대차보호법",
                    "article": "제11조",
                    "summary": "임차물 보존 의무",
                    "url": None,
                },
                "recommendation": "수선비 부담 범위를 명확히 협의하세요.",
                "is_favorable": False,
                "severity_reason": "수선 책임 전가",
            },
            {
                "id": str(uuid.uuid4()),
                "risk": "caution",
                "clause_number": "특약사항",
                "original_text": "보증금 반환 거절 시 연 12%의 이자를 가산한다.",
                "explanation": "임차인에게 유리한 조항입니다.",
                "law_reference": {
                    "law_name": "주택임대차보호법",
                    "article": "관련 조항",
                    "summary": "보증금 보호",
                    "url": None,
                },
                "recommendation": "특약사항에 명시 확인하세요.",
                "is_favorable": True,
                "severity_reason": "임차인 보호 조항",
            },
            {
                "id": str(uuid.uuid4()),
                "risk": "safe",
                "clause_number": "제1조",
                "original_text": "본 계약은 임대차 계약을 체결함을 목적으로 한다.",
                "explanation": "",
                "law_reference": None,
                "recommendation": None,
                "is_favorable": None,
                "severity_reason": None,
            },
        ],
        "summary": {"high": 0, "medium": 1, "caution": 1, "safe": 1},
        "special_clauses": ["보증금 반환 거절 시 연 12%의 이자를 가산한다."],
        "disclaimer": "본 분석은 법률 조언이 아닌 정보 제공 서비스입니다.",
        "ocr_method": "plain_text",
        "ocr_confidence": 1.0,
        "elapsed_seconds": 12.5,
    }


@pytest.fixture
def sample_contract_model(sample_contract_result, mock_user):
    """DB Contract 모델 모의 오브젝트."""
    contract = MagicMock()
    contract.id = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    contract.job_id = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
    contract.report_id = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
    contract.user_id = mock_user.id
    contract.s3_key = "contracts/test/test.pdf"
    contract.contract_type = "jeonse"
    contract.status = "completed"
    contract.progress = 100
    contract.current_step = "clause"
    contract.completed_steps = ["upload", "ocr", "analyze", "clause"]
    contract.result = sample_contract_result
    contract.ocr_text = "주택 임대차 계약서 전문 텍스트"
    contract.error_code = None
    contract.error_message = None
    contract.created_at = datetime.now(timezone.utc)
    contract.completed_at = datetime.now(timezone.utc)
    return contract
