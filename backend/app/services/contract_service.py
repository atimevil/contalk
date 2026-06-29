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
        quota.quota_type.startswith("pass_")
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


def _compute_risk_level(summary: dict) -> str:
    """
    하이브리드 등급 판정 알고리즘 (개수 + 비율).

    과거엔 표준 의무 조항이 blunt 규칙에 걸려 정상 계약서도 medium 2~4개가 나와
    개수 기반 승격을 쓸 수 없었다. 이제 classifier의 '표준 안전 베이스라인'
    (_STANDARD_SAFE_PATTERNS)이 표준 조항을 safe로 고정하므로, 정상 계약서의
    medium은 0에 수렴한다. 따라서 medium은 다시 '개수'로도 승격한다 —
    표준에서 벗어난 불리 '특약'은 개별 조항으로 분리되어 medium으로 잡히므로,
    그런 특약이 2개 이상이면 계약서 전체를 위험으로 본다.

    high(치명 위험, _CRITICAL_PATTERNS)는 1개라도 있으면 위험(미탐 0 바닥).

    1. high>=1 / medium>=2 → '🚨 위험'
    2. medium==1 / caution>=1 → '⚠️ 주의'
    3. 그 외 → '✅ 정상'

    (과거의 medium 비중 50%+ 조건은 medium>=2 규칙과 중복이고, safe가 없는
     격리 입력에서 medium==1을 high로 잘못 승격시켜 제거했다.)
    """
    high = summary.get("high", 0)
    medium = summary.get("medium", 0)
    caution = summary.get("caution", 0)

    if high >= 1 or medium >= 2:
        return "high"
    elif medium == 1 or caution >= 1:
        return "caution"
    return "safe"


def _compute_risk_score(summary: dict) -> int:
    """
    _compute_risk_level 등급과 밴드가 100% 매칭되는 보정 점수(0~100).
    - 위험군 (Red, 60~100)
    - 주의군 (Amber, 20~39)
    - 정상군 (Green, <20)
    등급을 먼저 구해 밴드 일치를 보장하고, 밴드 내에서 high 개수·medium 비중으로 가중한다.
    """
    high = summary.get("high", 0)
    medium = summary.get("medium", 0)
    caution = summary.get("caution", 0)
    safe = summary.get("safe", 0)
    total = high + medium + caution + safe
    medium_ratio = (medium / total) if total else 0.0

    level = _compute_risk_level(summary)
    if level == "high":
        return min(100, 60 + high * 12 + int(medium_ratio * 30))
    elif level == "caution":
        return min(39, 20 + high * 8 + int(medium_ratio * 20) + caution * 2)
    else:
        return min(19, 5 + int(medium_ratio * 20) + caution * 3)


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
                special_clause_draft=c.get("special_clause_draft"),
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
    risk_level = _compute_risk_level(normalized_summary)
    risk_score = _compute_risk_score(normalized_summary)

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
        risk_level = _compute_risk_level(normalized)
        risk_score = _compute_risk_score(normalized)
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
