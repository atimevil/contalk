import uuid
import httpx
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.payment import Payment
from app.models.quota import UserQuotaRecord
from app.schemas.payment import (
    PaymentPrepareResponse,
    PaymentVerifyResponse,
    PaymentRecord,
    PaymentHistoryResponse,
    PLAN_LABELS,
)
from app.schemas.auth import UserQuota
from app.schemas.common import PaginationMeta, DISCLAIMER
from app.core.config import settings

PORTONE_V2_API_URL = "https://api.portone.io"

PLAN_PRICES = {
    "single": settings.PRICE_SINGLE,
    "pass_1month": settings.PRICE_PASS_1MONTH,
    "pass_3month": settings.PRICE_PASS_3MONTH,
}


async def prepare_payment(
    db: AsyncSession, user_id: uuid.UUID, plan: str
) -> PaymentPrepareResponse:
    amount = PLAN_PRICES.get(plan)
    if amount is None:
        raise ValueError("VALIDATION_ERROR")

    merchant_uid = f"ct_{plan[:4]}_{uuid.uuid4().hex[:16]}"

    payment = Payment(
        user_id=user_id,
        plan=plan,
        amount=amount,
        status="pending",
        merchant_uid=merchant_uid,
    )
    db.add(payment)
    await db.flush()

    return PaymentPrepareResponse(
        merchant_uid=merchant_uid,
        amount=amount,
        plan=plan,
        plan_label=PLAN_LABELS.get(plan, plan),
        pg_provider=settings.PORTONE_PG_PROVIDER,
        disclaimer=DISCLAIMER,
    )


async def verify_payment(
    db: AsyncSession, user_id: uuid.UUID, imp_uid: str, merchant_uid: str
) -> PaymentVerifyResponse:
    """포트원 V2 결제 검증. merchant_uid가 V2 paymentId 역할을 한다."""
    payment_id = merchant_uid  # V2: 프론트가 paymentId로 merchant_uid를 사용

    # 중복 검증 방지
    dup_result = await db.execute(
        select(Payment).where(Payment.portone_uid == payment_id)
    )
    if dup_result.scalar_one_or_none():
        raise ValueError("PAYMENT_ALREADY_USED")

    # pending 결제 레코드 조회
    result = await db.execute(
        select(Payment).where(
            Payment.merchant_uid == merchant_uid,
            Payment.user_id == user_id,
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise ValueError("PAYMENT_VERIFY_FAILED")

    # 포트원 V2 결제 단건 조회
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{PORTONE_V2_API_URL}/payments/{payment_id}",
                headers={"Authorization": f"PortOne {settings.PORTONE_V2_API_SECRET}"},
            )
        if resp.status_code != 200:
            payment.status = "failed"
            await db.flush()
            raise RuntimeError("PAYMENT_VERIFY_FAILED")

        portone_payment = resp.json()
        portone_status = portone_payment.get("status")
        # V2 금액 구조: { amount: { total: int } }
        portone_amount = (portone_payment.get("amount") or {}).get("total", 0)

        if portone_amount != payment.amount:
            payment.status = "failed"
            await db.flush()
            raise ValueError("PAYMENT_AMOUNT_MISMATCH")

        if portone_status != "PAID":
            payment.status = "failed"
            await db.flush()
            raise ValueError("PAYMENT_VERIFY_FAILED")

    except (httpx.RequestError, KeyError) as e:
        payment.status = "failed"
        await db.flush()
        raise RuntimeError("PAYMENT_VERIFY_FAILED") from e

    # 결제 완료 처리
    now = datetime.now(timezone.utc)
    payment.status = "paid"
    payment.portone_uid = payment_id
    payment.paid_at = now

    if payment.plan == "pass_1month":
        payment.expires_at = now + timedelta(days=30)
    elif payment.plan == "pass_3month":
        payment.expires_at = now + timedelta(days=90)

    await db.flush()

    # Update user quota
    quota_result = await db.execute(
        select(UserQuotaRecord).where(UserQuotaRecord.user_id == user_id)
    )
    quota = quota_result.scalar_one_or_none()
    if not quota:
        quota = UserQuotaRecord(user_id=user_id)
        db.add(quota)

    if payment.plan == "single":
        quota.quota_type = "single"
        quota.remaining = (quota.remaining if quota.remaining > 0 else 0) + 1
    elif payment.plan in ("pass_1month", "pass_3month"):
        quota.quota_type = payment.plan
        quota.remaining = -1  # unlimited
        quota.pass_expires_at = payment.expires_at

    await db.flush()

    user_quota = UserQuota(
        type=quota.quota_type,
        remaining=quota.remaining,
        pass_expires_at=quota.pass_expires_at.isoformat() if quota.pass_expires_at else None,
    )

    return PaymentVerifyResponse(
        payment_id=str(payment.id),
        plan=payment.plan,
        amount=payment.amount,
        paid_at=payment.paid_at.isoformat(),
        quota=user_quota,
        disclaimer=DISCLAIMER,
    )


async def process_webhook(
    db: AsyncSession, imp_uid: str, merchant_uid: str, status: str
) -> None:
    """Process Portone webhook - update payment status."""
    result = await db.execute(
        select(Payment).where(Payment.merchant_uid == merchant_uid)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        return  # Unknown payment, ignore

    if status == "cancelled":
        payment.status = "cancelled"
        # Revoke quota if was paid
        quota_result = await db.execute(
            select(UserQuotaRecord).where(UserQuotaRecord.user_id == payment.user_id)
        )
        quota = quota_result.scalar_one_or_none()
        if quota and payment.plan == "single" and quota.remaining > 0:
            quota.remaining -= 1
        elif quota and payment.plan in ("pass_1month", "pass_3month"):
            quota.quota_type = "none"
            quota.remaining = 0
            quota.pass_expires_at = None
        await db.flush()
    elif status == "failed":
        payment.status = "failed"
        await db.flush()


async def get_payment_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    per_page: int = 10,
) -> PaymentHistoryResponse:
    from sqlalchemy import func

    offset = (page - 1) * per_page

    result = await db.execute(
        select(Payment)
        .where(Payment.user_id == user_id, Payment.status != "pending")
        .order_by(desc(Payment.created_at))
        .limit(per_page)
        .offset(offset)
    )
    payments = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).select_from(Payment).where(
            Payment.user_id == user_id, Payment.status != "pending"
        )
    )
    total = count_result.scalar()

    records = []
    for p in payments:
        records.append(
            PaymentRecord(
                id=str(p.id),
                plan=p.plan,
                plan_label=PLAN_LABELS.get(p.plan, p.plan),
                amount=p.amount,
                status=p.status,
                paid_at=(p.paid_at or p.created_at).isoformat(),
                expires_at=p.expires_at.isoformat() if p.expires_at else None,
            )
        )

    total_pages = max(1, (total + per_page - 1) // per_page)
    return PaymentHistoryResponse(
        payments=records,
        meta=PaginationMeta(
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        ),
        disclaimer=DISCLAIMER,
    )
