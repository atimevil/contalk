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

PORTONE_API_URL = "https://api.iamport.kr"

PLAN_PRICES = {
    "single": settings.PRICE_SINGLE,
    "pass_3month": settings.PRICE_PASS_3MONTH,
}


async def _get_portone_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{PORTONE_API_URL}/users/getToken",
            json={
                "imp_key": settings.PORTONE_IMP_KEY,
                "imp_secret": settings.PORTONE_IMP_SECRET,
            },
        )
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError("PAYMENT_VERIFY_FAILED")
        return data["response"]["access_token"]


async def prepare_payment(
    db: AsyncSession, user_id: uuid.UUID, plan: str
) -> PaymentPrepareResponse:
    amount = PLAN_PRICES.get(plan)
    if amount is None:
        raise ValueError("VALIDATION_ERROR")

    merchant_uid = f"contalktok_{plan}_{user_id}_{int(datetime.now(timezone.utc).timestamp())}"

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
    # Check for duplicate verification
    dup_result = await db.execute(
        select(Payment).where(Payment.portone_uid == imp_uid)
    )
    if dup_result.scalar_one_or_none():
        raise ValueError("PAYMENT_ALREADY_USED")

    # Get pending payment record
    result = await db.execute(
        select(Payment).where(
            Payment.merchant_uid == merchant_uid,
            Payment.user_id == user_id,
        )
    )
    payment = result.scalar_one_or_none()
    if not payment:
        raise ValueError("PAYMENT_VERIFY_FAILED")

    # Verify with Portone
    try:
        token = await _get_portone_token()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{PORTONE_API_URL}/payments/{imp_uid}",
                headers={"Authorization": token},
            )
            portone_data = resp.json()

        if portone_data.get("code") != 0:
            raise RuntimeError("PAYMENT_VERIFY_FAILED")

        portone_payment = portone_data["response"]
        portone_amount = portone_payment.get("amount", 0)
        portone_status = portone_payment.get("status")

        # Verify amount matches
        if portone_amount != payment.amount:
            payment.status = "failed"
            await db.flush()
            raise ValueError("PAYMENT_AMOUNT_MISMATCH")

        if portone_status != "paid":
            payment.status = "failed"
            await db.flush()
            raise ValueError("PAYMENT_VERIFY_FAILED")

    except (httpx.RequestError, KeyError) as e:
        payment.status = "failed"
        await db.flush()
        raise RuntimeError("PAYMENT_VERIFY_FAILED") from e

    # Mark payment as paid
    now = datetime.now(timezone.utc)
    payment.status = "paid"
    payment.portone_uid = imp_uid
    payment.paid_at = now

    if payment.plan == "pass_3month":
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
    elif payment.plan == "pass_3month":
        quota.quota_type = "pass_3month"
        quota.remaining = -1  # unlimited
        quota.pass_expires_at = payment.expires_at

    await db.flush()

    user_quota = UserQuota(
        type=quota.quota_type,
        remaining=quota.remaining,
        pass_expires_at=quota.pass_expires_at.isoformat() if quota.pass_expires_at else None,
    )

    return PaymentVerifyResponse(
        success=True,
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
        elif quota and payment.plan == "pass_3month":
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
