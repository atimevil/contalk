from typing import Optional, Literal, List
from pydantic import BaseModel

from app.schemas.auth import UserQuota
from app.schemas.common import CamelModel, DISCLAIMER, PaginationMeta

Plan = Literal["single", "pass_3month"]
PaymentStatus = Literal["paid", "cancelled", "failed", "pending"]

PLAN_LABELS = {
    "single": "건당 이용권",
    "pass_3month": "3개월 패스",
}


class PaymentPrepareRequest(CamelModel):
    plan: Plan


class PaymentPrepareResponse(CamelModel):
    merchant_uid: str
    amount: int
    plan: Plan
    plan_label: str
    pg_provider: str
    disclaimer: str = DISCLAIMER


class PaymentVerifyRequest(CamelModel):
    imp_uid: str
    merchant_uid: str


class PaymentVerifyResponse(CamelModel):
    success: bool = True
    payment_id: str
    plan: Plan
    amount: int
    paid_at: str  # ISO 8601
    quota: UserQuota
    disclaimer: str = DISCLAIMER


class PaymentRecord(CamelModel):
    id: str
    plan: Plan
    plan_label: str
    amount: int
    status: PaymentStatus
    paid_at: str
    expires_at: Optional[str] = None


class PaymentHistoryResponse(CamelModel):
    payments: List[PaymentRecord]
    meta: PaginationMeta
    disclaimer: str = DISCLAIMER


class PortOneWebhookBody(CamelModel):
    imp_uid: str
    merchant_uid: str
    status: Literal["paid", "cancelled", "failed"]


class WebhookResponse(CamelModel):
    received: bool = True
