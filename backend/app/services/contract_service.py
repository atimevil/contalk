import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models.contract import Contract
from app.models.quota import UserQuotaRecord
from app.schemas.analysis import (
    AnalysisStatusResponse,
    AnalysisResultResponse,
    AnalysisClause,
    LawReference,
    RiskSummary,
    AnalysisHistoryItem,
)
from app.schemas.common import DISCLAIMER


async def check_and_consume_quota(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Check if user has quota. Raises ValueError with error code if not."""
    result = await db.execute(
        select(UserQuotaRecord).where(UserQuotaRecord.user_id == user_id)
    )
    quota = result.scalar_one_or_none()

    if not quota or quota.quota_type == "none" or quota.remaining == 0:
        raise ValueError("QUOTA_EXCEEDED")

    # Check pass expiry
    if (
        quota.quota_type == "pass_3month"
        and quota.pass_expires_at
        and quota.pass_expires_at < datetime.now(timezone.utc)
    ):
        quota.quota_type = "none"
        quota.remaining = 0
        await db.flush()
        raise ValueError("QUOTA_EXCEEDED")

    # Consume one use (unless unlimited)
    if quota.remaining != -1:
        quota.remaining -= 1
    await db.flush()


async def create_contract(
    db: AsyncSession,
    user_id: uuid.UUID,
    s3_key: str,
    contract_type: str = "unknown",
) -> Contract:
    contract = Contract(
        user_id=user_id,
        s3_key=s3_key,
        contract_type=contract_type,
        status="queued",
        progress=0,
        current_step="upload",
        completed_steps=[],
    )
    db.add(contract)
    await db.flush()
    return contract


async def get_contract_by_job_id(
    db: AsyncSession, job_id: uuid.UUID
) -> Optional[Contract]:
    result = await db.execute(
        select(Contract).where(Contract.job_id == job_id)
    )
    return result.scalar_one_or_none()


async def get_contract_by_report_id(
    db: AsyncSession, report_id: uuid.UUID
) -> Optional[Contract]:
    result = await db.execute(
        select(Contract).where(Contract.report_id == report_id)
    )
    return result.scalar_one_or_none()


def contract_to_status_response(contract: Contract) -> AnalysisStatusResponse:
    return AnalysisStatusResponse(
        job_id=str(contract.job_id),
        status=contract.status,
        progress=contract.progress,
        current_step=contract.current_step,
        completed_steps=contract.completed_steps or [],
        report_id=str(contract.report_id) if contract.report_id else None,
        error_code=contract.error_code,
        error_message=contract.error_message,
        disclaimer=DISCLAIMER,
    )


def _compute_risk_score(summary: dict) -> int:
    """Compute 0-100 risk score from clause summary."""
    high = summary.get("high", 0)
    medium = summary.get("medium", 0)
    caution = summary.get("caution", 0)
    safe = summary.get("safe", 0)
    total = high + medium + caution + safe
    if total == 0:
        return 0
    weighted = (high * 3 + medium * 2 + caution * 1) / (total * 3)
    return min(100, int(weighted * 100))


def _compute_risk_level(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    if score >= 20:
        return "caution"
    return "safe"


def contract_to_result_response(contract: Contract) -> AnalysisResultResponse:
    result = contract.result or {}
    raw_clauses = result.get("clauses", [])

    clauses = []
    for c in raw_clauses:
        law_ref = None
        if c.get("law_reference"):
            lr = c["law_reference"]
            law_ref = LawReference(
                law_name=lr.get("law_name", ""),
                article=lr.get("article", ""),
                summary=lr.get("summary", ""),
                url=lr.get("url"),
            )
        clauses.append(
            AnalysisClause(
                id=c.get("id", str(uuid.uuid4())),
                risk=c.get("risk", "safe"),
                clause_number=c.get("clause_number"),
                original_text=c.get("original_text", c.get("text", "")),
                explanation=c.get("explanation", ""),
                law_reference=law_ref,
                recommendation=c.get("recommendation"),
            )
        )

    summary_raw = result.get("summary", {"high": 0, "medium": 0, "caution": 0, "safe": 0})
    # BUG-004 fix: AI pipeline은 "normal" 키를 사용하고, 백엔드/프론트는 "safe" 키를 사용한다.
    # pipeline 결과의 "normal" 값을 "safe"로 정규화한다.
    safe_count = summary_raw.get("safe", 0) + summary_raw.get("normal", 0)
    normalized_summary = {
        "high": summary_raw.get("high", 0),
        "medium": summary_raw.get("medium", 0),
        "caution": summary_raw.get("caution", 0),
        "safe": safe_count,
    }
    summary = RiskSummary(
        high=normalized_summary["high"],
        medium=normalized_summary["medium"],
        caution=normalized_summary["caution"],
        safe=normalized_summary["safe"],
    )
    risk_score = _compute_risk_score(normalized_summary)
    risk_level = _compute_risk_level(risk_score)

    return AnalysisResultResponse(
        report_id=str(contract.report_id),
        job_id=str(contract.job_id),
        created_at=contract.created_at.isoformat(),
        contract_type=contract.contract_type,
        risk_score=risk_score,
        risk_level=risk_level,
        summary=summary,
        clauses=clauses,
        ocr_text=contract.ocr_text,
        disclaimer=DISCLAIMER,
    )


async def get_analysis_history(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    per_page: int = 10,
) -> tuple[List[AnalysisHistoryItem], int]:
    offset = (page - 1) * per_page
    result = await db.execute(
        select(Contract)
        .where(
            Contract.user_id == user_id,
            Contract.status == "completed",
            Contract.report_id.is_not(None),
        )
        .order_by(desc(Contract.created_at))
        .limit(per_page)
        .offset(offset)
    )
    contracts = result.scalars().all()

    from sqlalchemy import func
    count_result = await db.execute(
        select(func.count()).select_from(Contract).where(
            Contract.user_id == user_id,
            Contract.status == "completed",
            Contract.report_id.is_not(None),
        )
    )
    total = count_result.scalar()

    items = []
    for c in contracts:
        summary_raw = (c.result or {}).get("summary", {"high": 0, "medium": 0, "caution": 0, "safe": 0})
        # BUG-004 fix: pipeline "normal" → "safe" 정규화 (history 조회 시에도 동일 적용)
        safe_count = summary_raw.get("safe", 0) + summary_raw.get("normal", 0)
        normalized = {
            "high": summary_raw.get("high", 0),
            "medium": summary_raw.get("medium", 0),
            "caution": summary_raw.get("caution", 0),
            "safe": safe_count,
        }
        risk_score = _compute_risk_score(normalized)
        risk_level = _compute_risk_level(risk_score)
        items.append(
            AnalysisHistoryItem(
                report_id=str(c.report_id),
                created_at=c.created_at.isoformat(),
                contract_type=c.contract_type,
                risk_score=risk_score,
                risk_level=risk_level,
                summary=RiskSummary(
                    high=normalized["high"],
                    medium=normalized["medium"],
                    caution=normalized["caution"],
                    safe=normalized["safe"],
                ),
            )
        )

    return items, total
