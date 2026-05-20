"""
Payment API endpoints.

POST /payment/prepare   — Prepare payment (get merchant_uid + amount)
POST /payment/verify    — Verify payment after Portone callback
GET  /payment/history   — Payment history (paginated)
POST /payment/webhook   — Portone server-to-server webhook
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_request_id, DISCLAIMER
from app.models.user import User
from app.schemas.payment import (
    PaymentPrepareRequest,
    PaymentPrepareResponse,
    PaymentVerifyRequest,
    PaymentVerifyResponse,
    PaymentHistoryResponse,
    PortOneWebhookBody,
    WebhookResponse,
)
from app.services import payment_service

router = APIRouter(prefix="/payment", tags=["payment"])


def _error(code: str, message: str, status_code: int, request_id: str):
    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error": {"code": code, "message": message},
            "request_id": request_id,
            "disclaimer": DISCLAIMER,
        },
    )


@router.post("/prepare", response_model=PaymentPrepareResponse, status_code=200)
async def prepare_payment(
    body: PaymentPrepareRequest,
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """결제 준비 — merchant_uid 및 금액 발급."""
    try:
        return await payment_service.prepare_payment(db, current_user.id, body.plan)
    except ValueError as e:
        _error("VALIDATION_ERROR", "유효하지 않은 결제 플랜입니다.", 400, request_id)


@router.post("/verify", response_model=PaymentVerifyResponse, status_code=200)
async def verify_payment(
    body: PaymentVerifyRequest,
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """결제 검증 (포트원 콜백 후 프론트엔드 호출)."""
    try:
        return await payment_service.verify_payment(
            db, current_user.id, body.imp_uid, body.merchant_uid
        )
    except ValueError as e:
        err_str = str(e)
        if "PAYMENT_ALREADY_USED" in err_str:
            _error("PAYMENT_ALREADY_USED", "이미 검증된 결제입니다.", 400, request_id)
        elif "PAYMENT_AMOUNT_MISMATCH" in err_str:
            _error("PAYMENT_AMOUNT_MISMATCH", "결제 금액이 일치하지 않습니다.", 400, request_id)
        elif "PAYMENT_VERIFY_FAILED" in err_str:
            _error("PAYMENT_VERIFY_FAILED", "결제 검증에 실패했습니다.", 500, request_id)
        raise
    except RuntimeError as e:
        _error("PAYMENT_VERIFY_FAILED", "포트원 서버 오류가 발생했습니다.", 500, request_id)


@router.get("/history", response_model=PaymentHistoryResponse, status_code=200)
async def get_payment_history(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=50, alias="perPage"),
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """결제 이력 조회."""
    return await payment_service.get_payment_history(db, current_user.id, page, per_page)


@router.post("/webhook", response_model=WebhookResponse, status_code=200)
async def portone_webhook(
    body: PortOneWebhookBody,
    db: AsyncSession = Depends(get_db),
):
    """
    포트원(iamport) 서버-서버 웹훅 수신.
    인증 불필요 — 포트원 IP 화이트리스트로 보호.
    """
    await payment_service.process_webhook(
        db, body.imp_uid, body.merchant_uid, body.status
    )
    return WebhookResponse(received=True)
