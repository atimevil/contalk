"""
Contract Analysis API endpoints.

POST /analysis/upload                              — Upload & start analysis
GET  /analysis/{job_id}/status                    — Poll analysis status
GET  /analysis/{report_id}/result                 — Get analysis result
GET  /analysis/{report_id}/pdf                    — Download result PDF
GET  /analysis/{report_id}/special-clauses        — Get special clause recommendations
GET  /analysis/{report_id}/special-clauses/pdf    — Download special clauses PDF
PATCH /analysis/{report_id}/special-clauses/{clause_id} — Update special clause text
GET  /analysis/history                            — Analysis history (paginated)
GET  /user/quota                                  — User remaining quota
"""
import uuid
import math
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from io import BytesIO

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_request_id, DISCLAIMER
from app.models.user import User
from app.models.contract import Contract
from app.models.special_clause import SpecialClauseEdit
from app.schemas.analysis import (
    UploadResponse,
    AnalysisStatusResponse,
    AnalysisResultResponse,
    AnalysisHistoryItem,
)
from app.schemas.special_clause import (
    SpecialClausesResponse,
    SpecialClause,
    UpdateSpecialClauseRequest,
    UpdateSpecialClauseResponse,
)
from app.schemas.auth import UserQuota
from app.schemas.common import PaginationMeta, DISCLAIMER as DISC
from app.services import contract_service, s3_service
from app.services.auth_service import get_user_quota

router = APIRouter(tags=["analysis"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "application/pdf"}
MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB


def _error(code: str, message: str, status_code: int, request_id: str):
    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error": {"code": code, "message": message},
            "request_id": request_id,
            "disclaimer": DISC,
        },
    )


@router.post("/analysis/upload", response_model=UploadResponse, status_code=202)
async def upload_contract(
    file: UploadFile = File(...),
    contract_type: str = Form(default="unknown"),
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """계약서 업로드 및 분석 시작."""
    # Validate file type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_CONTENT_TYPES:
        _error("FILE_TYPE_INVALID", "JPG, PNG, PDF 파일만 업로드 가능합니다.", 400, request_id)

    # Validate contract type
    if contract_type not in ("jeonse", "monthly", "unknown"):
        contract_type = "unknown"

    # Read file and check size
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE_BYTES:
        _error("FILE_SIZE_EXCEEDED", "파일 크기는 20MB를 초과할 수 없습니다.", 400, request_id)

    # Check quota
    try:
        await contract_service.check_and_consume_quota(db, current_user.id)
    except ValueError as e:
        if "QUOTA_EXCEEDED" in str(e):
            _error("QUOTA_EXCEEDED", "잔여 분석 횟수가 없습니다.", 402, request_id)
        raise

    # Upload to S3
    try:
        s3_key = await s3_service.upload_contract_file(
            file_content=file_content,
            original_filename=file.filename or "contract",
            user_id=str(current_user.id),
            content_type=content_type,
        )
    except RuntimeError:
        _error("FILE_UPLOAD_FAILED", "파일 업로드에 실패했습니다.", 500, request_id)

    # Create contract record
    contract = await contract_service.create_contract(
        db, current_user.id, s3_key, contract_type
    )
    await db.commit()

    # Dispatch Celery task
    from app.tasks.analysis import run_analysis_task
    run_analysis_task.delay(
        contract_id=str(contract.id),
        job_id=str(contract.job_id),
        s3_key=s3_key,
    )

    return UploadResponse(
        job_id=str(contract.job_id),
        estimated_seconds=60,
        status="queued",
        disclaimer=DISC,
    )


@router.get("/analysis/{job_id}/status", response_model=AnalysisStatusResponse)
async def get_analysis_status(
    job_id: str,
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """분석 상태 조회 (폴링용)."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        _error("ANALYSIS_NOT_FOUND", "유효하지 않은 jobId입니다.", 404, request_id)

    contract = await contract_service.get_contract_by_job_id(db, job_uuid)
    if not contract:
        _error("ANALYSIS_NOT_FOUND", "분석 작업을 찾을 수 없습니다.", 404, request_id)
    if contract.user_id != current_user.id:
        _error("FORBIDDEN", "접근 권한이 없습니다.", 403, request_id)

    return contract_service.contract_to_status_response(contract)


@router.get("/analysis/{report_id}/result", response_model=AnalysisResultResponse)
async def get_analysis_result(
    report_id: str,
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """분석 결과 조회."""
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        _error("ANALYSIS_NOT_FOUND", "유효하지 않은 reportId입니다.", 404, request_id)

    contract = await contract_service.get_contract_by_report_id(db, report_uuid)
    if not contract:
        _error("ANALYSIS_NOT_FOUND", "분석 결과를 찾을 수 없습니다.", 404, request_id)
    if contract.user_id != current_user.id:
        _error("FORBIDDEN", "접근 권한이 없습니다.", 403, request_id)

    return contract_service.contract_to_result_response(contract)


@router.get("/analysis/{report_id}/pdf")
async def download_analysis_pdf(
    report_id: str,
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """분석 결과 PDF 다운로드."""
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        _error("ANALYSIS_NOT_FOUND", "유효하지 않은 reportId입니다.", 404, request_id)

    contract = await contract_service.get_contract_by_report_id(db, report_uuid)
    if not contract:
        _error("ANALYSIS_NOT_FOUND", "분석 결과를 찾을 수 없습니다.", 404, request_id)
    if contract.user_id != current_user.id:
        _error("FORBIDDEN", "접근 권한이 없습니다.", 403, request_id)

    from app.services.pdf_service import generate_analysis_pdf
    pdf_bytes = generate_analysis_pdf(report_id, contract.result or {})

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="contract_analysis_{report_id}.pdf"'
        },
    )


@router.get("/analysis/{report_id}/special-clauses", response_model=SpecialClausesResponse)
async def get_special_clauses(
    report_id: str,
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """추천 특약사항 목록 조회."""
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        _error("ANALYSIS_NOT_FOUND", "유효하지 않은 reportId입니다.", 404, request_id)

    contract = await contract_service.get_contract_by_report_id(db, report_uuid)
    if not contract:
        _error("ANALYSIS_NOT_FOUND", "분석 결과를 찾을 수 없습니다.", 404, request_id)
    if contract.user_id != current_user.id:
        _error("FORBIDDEN", "접근 권한이 없습니다.", 403, request_id)

    result = contract.result or {}
    raw_clauses = result.get("clauses", [])
    special_texts = result.get("special_clauses", [])

    # Get any user edits
    edits_result = await db.execute(
        select(SpecialClauseEdit).where(SpecialClauseEdit.contract_id == contract.id)
    )
    edits_map = {e.clause_id: e for e in edits_result.scalars().all()}

    # Build special clauses from high/medium risk clauses
    clauses = []
    category_map = {
        "high": "deposit",
        "medium": "renewal",
        "caution": "repair",
    }
    for i, c in enumerate(raw_clauses):
        risk = c.get("risk", "safe")
        if risk not in ("high", "medium", "caution"):
            continue

        clause_id = c.get("id", f"clause_{i}")
        # Use special_texts if available, else generate from recommendation
        if i < len(special_texts):
            text = special_texts[i]
        else:
            text = c.get("recommendation", f"특약: {c.get('original_text', '')[:100]}")

        # Apply user edit if exists
        if clause_id in edits_map:
            text = edits_map[clause_id].edited_text

        clauses.append(
            SpecialClause(
                id=clause_id,
                related_risk_clause_id=clause_id,
                related_risk=risk,
                title=f"{c.get('clause_number', '특약')} 관련 특약",
                text=text,
                category=category_map.get(risk, "other"),
                is_editable=True,
            )
        )

    return SpecialClausesResponse(
        report_id=report_id,
        clauses=clauses,
        disclaimer=DISC,
    )


@router.get("/analysis/{report_id}/special-clauses/pdf")
async def download_special_clauses_pdf(
    report_id: str,
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특약사항 초안 PDF 다운로드."""
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        _error("ANALYSIS_NOT_FOUND", "유효하지 않은 reportId입니다.", 404, request_id)

    contract = await contract_service.get_contract_by_report_id(db, report_uuid)
    if not contract:
        _error("ANALYSIS_NOT_FOUND", "분석 결과를 찾을 수 없습니다.", 404, request_id)
    if contract.user_id != current_user.id:
        _error("FORBIDDEN", "접근 권한이 없습니다.", 403, request_id)

    result = contract.result or {}
    special_texts = result.get("special_clauses", [])
    clauses = [{"title": f"특약 {i + 1}", "text": t} for i, t in enumerate(special_texts)]

    from app.services.pdf_service import generate_special_clauses_pdf
    pdf_bytes = generate_special_clauses_pdf(report_id, clauses)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="special_clauses_{report_id}.pdf"'
        },
    )


@router.patch(
    "/analysis/{report_id}/special-clauses/{clause_id}",
    response_model=UpdateSpecialClauseResponse,
)
async def update_special_clause(
    report_id: str,
    clause_id: str,
    body: UpdateSpecialClauseRequest,
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """특약 문구 사용자 수정 저장."""
    try:
        report_uuid = uuid.UUID(report_id)
    except ValueError:
        _error("ANALYSIS_NOT_FOUND", "유효하지 않은 reportId입니다.", 404, request_id)

    contract = await contract_service.get_contract_by_report_id(db, report_uuid)
    if not contract:
        _error("ANALYSIS_NOT_FOUND", "분석 결과를 찾을 수 없습니다.", 404, request_id)
    if contract.user_id != current_user.id:
        _error("FORBIDDEN", "접근 권한이 없습니다.", 403, request_id)

    # Upsert edit record
    result = await db.execute(
        select(SpecialClauseEdit).where(
            SpecialClauseEdit.contract_id == contract.id,
            SpecialClauseEdit.clause_id == clause_id,
        )
    )
    edit = result.scalar_one_or_none()

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)

    if edit:
        edit.edited_text = body.text
        edit.updated_at = now
    else:
        edit = SpecialClauseEdit(
            contract_id=contract.id,
            clause_id=clause_id,
            edited_text=body.text,
            updated_at=now,
        )
        db.add(edit)

    await db.flush()

    return UpdateSpecialClauseResponse(
        id=clause_id,
        text=body.text,
        updated_at=now.isoformat(),
        disclaimer=DISC,
    )


@router.get("/analysis/history")
async def get_analysis_history(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=10, ge=1, le=50, alias="perPage"),
    request_id: str = Depends(get_request_id),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """분석 이력 목록 조회."""
    items, total = await contract_service.get_analysis_history(
        db, current_user.id, page, per_page
    )
    total_pages = max(1, math.ceil(total / per_page))

    return {
        "success": True,
        "data": {
            "analyses": [item.model_dump() for item in items],
        },
        "meta": {
            "total": total,
            "page": page,
            "per_page": per_page,
            "total_pages": total_pages,
        },
        "disclaimer": DISC,
    }


@router.get("/user/quota", response_model=UserQuota)
async def get_quota(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """잔여 할당량 조회."""
    return await get_user_quota(db, current_user.id)
