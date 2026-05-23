"""
Celery tasks for contract analysis.

This task orchestrates the analysis pipeline:
1. Update status to 'ocr'
2. Call AI pipeline (run_full_pipeline)
3. Convert pipeline result to DB format
4. Store result, update status to 'completed'
"""
import re
import uuid
from datetime import datetime, timezone
from celery import shared_task
from sqlalchemy import select

from app.tasks.celery_app import celery_app
from app.core.database import AsyncSessionLocal


# ─── 법령명 목록 (parse_law_ref 에서 사용) ─────────────────────────────────
_KNOWN_LAW_NAMES = [
    "주택임대차보호법",
    "상가건물 임대차보호법",
    "상가건물임대차보호법",
    "민법",
    "공인중개사법",
    "주거기본법",
]


def _parse_law_ref(law_ref_str: str) -> tuple[str, str]:
    """
    "주택임대차보호법 제3조 제1항" → ("주택임대차보호법", "제3조 제1항")
    "민법 제623조"                 → ("민법", "제623조")
    "(관련 조항 확인 권장)"          → ("주택임대차보호법", "관련 조항 확인 필요")
    """
    if not law_ref_str:
        return "", ""

    for law_name in _KNOWN_LAW_NAMES:
        if law_ref_str.startswith(law_name):
            article = law_ref_str[len(law_name):].strip()
            # 괄호 안에 안내 문구만 있는 경우 정리
            article = re.sub(r"^\((.+)\)$", r"\1", article).strip()
            return law_name, article

    # 알 수 없는 법령명이면 전체를 law_name 으로 처리
    return law_ref_str, ""


def _convert_pipeline_result(pipeline_result: dict, contract_id: str) -> dict:
    """
    ai.pipeline.run_full_pipeline() 반환값을 DB 저장 형식으로 변환한다.

    Pipeline 형식:
        {
            "status": "completed",
            "raw_text": str,
            "ocr_method": str,
            "ocr_confidence": float,
            "risk_summary": {"high": 0, "medium": 1, "caution": 1, "safe": 3},
            "clauses": [
                {
                    "number": "제4조",
                    "title": "",
                    "text": "...",
                    "risk": "medium",
                    "items": [],
                    "law_ref": "주택임대차보호법 제7조",
                    "law_summary": "...",
                    "is_favorable": False,
                    "explanation": "...",
                    "tenant_action": "...",
                    "severity_reason": "...",
                }
            ],
            "special_clauses": ["..."],
            "disclaimer": "...",
        }

    DB 저장 형식:
        {
            "contract_id": str,
            "clauses": [
                {
                    "id": uuid_str,
                    "risk": "medium",
                    "clause_number": "제4조",
                    "original_text": "...",
                    "explanation": "...",
                    "law_reference": {
                        "law_name": "주택임대차보호법",
                        "article": "제7조",
                        "summary": "...",
                        "url": null,
                    },
                    "recommendation": "...",
                    "is_favorable": False,
                    "severity_reason": "...",
                }
            ],
            "summary": {"high": 0, "medium": 1, "caution": 1, "safe": 3},
            "special_clauses": ["..."],
            "disclaimer": "...",
            "ocr_method": "...",
            "ocr_confidence": 0.0,
            "elapsed_seconds": 0.0,
        }
    """
    raw_clauses = pipeline_result.get("clauses", [])
    converted_clauses = []

    for clause in raw_clauses:
        law_ref_str = clause.get("law_ref") or ""
        law_summary = clause.get("law_summary") or ""

        law_name, article = _parse_law_ref(law_ref_str)

        law_reference = None
        if law_name or article:
            law_reference = {
                "law_name": law_name,
                "article": article,
                "summary": law_summary,
                "url": None,
            }

        converted_clauses.append(
            {
                "id": str(uuid.uuid4()),
                "risk": clause.get("risk", "safe"),
                "clause_number": clause.get("number"),
                "original_text": clause.get("text", ""),
                "explanation": clause.get("explanation") or "",
                "law_reference": law_reference,
                "recommendation": clause.get("tenant_action"),
                "is_favorable": clause.get("is_favorable"),
                "severity_reason": clause.get("severity_reason"),
            }
        )

    risk_summary = pipeline_result.get("risk_summary", {})

    return {
        "contract_id": contract_id,
        "clauses": converted_clauses,
        "summary": {
            "high": risk_summary.get("high", 0),
            "medium": risk_summary.get("medium", 0),
            "caution": risk_summary.get("caution", 0),
            "safe": risk_summary.get("safe", 0),
        },
        "special_clauses": pipeline_result.get("special_clauses", []),
        "disclaimer": pipeline_result.get("disclaimer", ""),
        "ocr_method": pipeline_result.get("ocr_method", ""),
        "ocr_confidence": pipeline_result.get("ocr_confidence", 0.0),
        "elapsed_seconds": pipeline_result.get("elapsed_seconds", 0.0),
    }


def _sync_update_contract_status(
    contract_job_id: str,
    status: str,
    progress: int,
    current_step: str,
    completed_steps: list,
    result: dict = None,
    error_code: str = None,
    error_message: str = None,
    report_id: str = None,
    ocr_text: str = None,
):
    """Synchronous DB update for use within Celery (uses async SQLAlchemy via asyncio.run)."""
    import asyncio
    from app.models.contract import Contract

    async def _update():
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                select(Contract).where(Contract.job_id == uuid.UUID(contract_job_id))
            )
            contract = res.scalar_one_or_none()
            if not contract:
                return

            contract.status = status
            contract.progress = progress
            contract.current_step = current_step
            contract.completed_steps = completed_steps

            if result is not None:
                contract.result = result
            if error_code is not None:
                contract.error_code = error_code
            if error_message is not None:
                contract.error_message = error_message
            if report_id is not None:
                contract.report_id = uuid.UUID(report_id)
            if ocr_text is not None:
                contract.ocr_text = ocr_text
            if status == "completed":
                contract.completed_at = datetime.now(timezone.utc)

            await db.commit()

    asyncio.run(_update())


@celery_app.task(name="analysis.run_analysis", bind=True, max_retries=2)
def run_analysis_task(self, contract_id: str, job_id: str, s3_key: str):
    """
    Main Celery task for running AI contract analysis.

    Calls ai.pipeline.run_full_pipeline and converts the result to DB format.
    """
    try:
        # ── Step 1: OCR 시작 상태 업데이트 ──────────────────────────────────
        _sync_update_contract_status(
            contract_job_id=job_id,
            status="ocr",
            progress=20,
            current_step="ocr",
            completed_steps=["upload"],
        )

        # ── Step 2: 분석 시작 상태 업데이트 ──────────────────────────────────
        _sync_update_contract_status(
            contract_job_id=job_id,
            status="analyzing",
            progress=50,
            current_step="analyze",
            completed_steps=["upload", "ocr"],
        )

        # ── Step 3: AI 파이프라인 실행 ────────────────────────────────────────
        from ai.pipeline import run_full_pipeline

        pipeline_result = run_full_pipeline(
            contract_id=contract_id,
            s3_key=s3_key,
        )

        # 파이프라인 실패 처리
        if pipeline_result.get("status") == "failed":
            raise RuntimeError(
                pipeline_result.get("error") or "AI 파이프라인 실행 실패"
            )

        # ── Step 4: 결과 형식 변환 ───────────────────────────────────────────
        db_result = _convert_pipeline_result(pipeline_result, contract_id)

        # ocr_text 는 별도 컬럼에 저장 (contract.ocr_text)
        ocr_text = pipeline_result.get("raw_text", "")

        # ── Step 5: 특약사항 생성 중 상태 업데이트 ───────────────────────────
        _sync_update_contract_status(
            contract_job_id=job_id,
            status="generating",
            progress=80,
            current_step="clause",
            completed_steps=["upload", "ocr", "analyze"],
        )

        # ── Step 6: 완료 처리 ────────────────────────────────────────────────
        new_report_id = str(uuid.uuid4())
        _sync_update_contract_status(
            contract_job_id=job_id,
            status="completed",
            progress=100,
            current_step="clause",
            completed_steps=["upload", "ocr", "analyze", "clause"],
            result=db_result,
            report_id=new_report_id,
            ocr_text=ocr_text[:10_000] if ocr_text else None,  # DB 컬럼 크기 제한
        )

    except Exception as exc:
        error_msg = str(exc)
        if "timeout" in error_msg.lower():
            error_code = "ANALYSIS_TIMEOUT"
        elif "OCR" in error_msg:
            error_code = "OCR_FAILED"
        else:
            error_code = "INTERNAL_SERVER_ERROR"

        _sync_update_contract_status(
            contract_job_id=job_id,
            status="failed",
            progress=0,
            current_step="analyze",
            completed_steps=[],
            error_code=error_code,
            error_message=error_msg,
        )
        # 일시적 오류 (네트워크, 타임아웃 등)에 대해서만 재시도
        if not isinstance(exc, (ValueError, TypeError, FileNotFoundError)):
            raise self.retry(exc=exc, countdown=10)


def _build_placeholder_result(contract_id: str) -> dict:
    """
    AI 파이프라인을 사용할 수 없을 때의 플레이스홀더 결과.
    테스트/디버깅 용도로만 사용한다.
    """
    return {
        "contract_id": contract_id,
        "clauses": [
            {
                "id": str(uuid.uuid4()),
                "risk": "medium",
                "clause_number": "제5조",
                "original_text": "임차인은 임대인 동의 없이 전대하거나 임차권을 양도할 수 없다.",
                "explanation": "임차인에게 불리한 조항입니다. 임차인의 권리 행사가 제한됩니다.",
                "law_reference": {
                    "law_name": "주택임대차보호법",
                    "article": "관련 조항",
                    "summary": "임차권 양도 제한",
                    "url": None,
                },
                "recommendation": "계약 전 임대인과 협의하여 예외 조건을 명시하세요.",
                "is_favorable": False,
                "severity_reason": "임차인의 권리 제한 조항",
            },
        ],
        "summary": {"high": 0, "medium": 1, "caution": 0, "safe": 0},
        "special_clauses": [],
        "disclaimer": "본 분석은 법률 조언이 아닌 정보 제공 서비스입니다. 중요한 사항은 전문 법률가에게 확인하세요.",
        "ocr_method": "placeholder",
        "ocr_confidence": 0.0,
        "elapsed_seconds": 0.0,
    }
