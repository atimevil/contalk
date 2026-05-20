"""
Celery tasks for contract analysis.

This task orchestrates the analysis pipeline:
1. Update status to 'ocr'
2. Call AI pipeline (run_full_pipeline stub)
3. Store result, update status to 'completed'
"""
import uuid
from datetime import datetime, timezone
from celery import shared_task
from sqlalchemy import select

from app.tasks.celery_app import celery_app
from app.core.database import AsyncSessionLocal


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
    """Synchronous DB update for use within Celery (uses sync SQLAlchemy)."""
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

    Calls ai/pipeline.run_full_pipeline (stub) once implemented by ai-engineer.
    """
    try:
        # Step 1: Mark as uploading/ocr
        _sync_update_contract_status(
            contract_job_id=job_id,
            status="ocr",
            progress=20,
            current_step="ocr",
            completed_steps=["upload"],
        )

        # Step 2: Mark as analyzing
        _sync_update_contract_status(
            contract_job_id=job_id,
            status="analyzing",
            progress=50,
            current_step="analyze",
            completed_steps=["upload", "ocr"],
        )

        # Step 3: Call AI pipeline
        # ai-engineer implements this; currently raises NotImplementedError
        from ai.pipeline import run_full_pipeline

        try:
            pipeline_result = run_full_pipeline(
                contract_id=contract_id,
                s3_key=s3_key,
            )
        except NotImplementedError:
            # AI pipeline not yet implemented — use placeholder result
            pipeline_result = _build_placeholder_result(contract_id)

        # Step 4: Generating special clauses step
        _sync_update_contract_status(
            contract_job_id=job_id,
            status="generating",
            progress=80,
            current_step="clause",
            completed_steps=["upload", "ocr", "analyze"],
        )

        # Step 5: Complete
        new_report_id = str(uuid.uuid4())
        _sync_update_contract_status(
            contract_job_id=job_id,
            status="completed",
            progress=100,
            current_step="clause",
            completed_steps=["upload", "ocr", "analyze", "clause"],
            result=pipeline_result,
            report_id=new_report_id,
        )

    except Exception as exc:
        error_msg = str(exc)
        error_code = "ANALYSIS_TIMEOUT" if "timeout" in error_msg.lower() else "INTERNAL_SERVER_ERROR"

        _sync_update_contract_status(
            contract_job_id=job_id,
            status="failed",
            progress=0,
            current_step="analyze",
            completed_steps=[],
            error_code=error_code,
            error_message=error_msg,
        )
        # Retry on transient errors (not on NotImplementedError escalation)
        if not isinstance(exc, (ValueError, TypeError)):
            raise self.retry(exc=exc, countdown=10)


def _build_placeholder_result(contract_id: str) -> dict:
    """
    Placeholder analysis result used when AI pipeline is not yet implemented.
    ai-engineer should replace this by implementing run_full_pipeline.
    """
    return {
        "contract_id": contract_id,
        "clauses": [
            {
                "id": str(uuid.uuid4()),
                "risk": "high",
                "clause_number": "제3조",
                "original_text": "임대인은 임차인의 동의 없이 임대물의 구조 변경 가능",
                "explanation": "임대인이 임차인 동의 없이 구조 변경할 수 있어 거주 안정성이 위협받을 수 있습니다.",
                "law_reference": {
                    "law_name": "주택임대차보호법",
                    "article": "제3조 제1항",
                    "summary": "임차인의 주거 안정을 보장해야 합니다.",
                    "url": "https://www.law.go.kr/",
                },
                "recommendation": "임차인 동의 없는 구조 변경을 금지하는 특약 추가를 권고합니다.",
            },
            {
                "id": str(uuid.uuid4()),
                "risk": "medium",
                "clause_number": "제5조",
                "original_text": "계약 종료 후 1개월 이내 보증금 반환",
                "explanation": "보증금 반환 기한이 법정 기한보다 길게 설정되어 있습니다.",
                "law_reference": {
                    "law_name": "주택임대차보호법",
                    "article": "제6조의2",
                    "summary": "계약 종료 시 즉시 보증금 반환이 원칙입니다.",
                    "url": "https://www.law.go.kr/",
                },
                "recommendation": "계약 종료 즉시 반환으로 수정을 협의하세요.",
            },
            {
                "id": str(uuid.uuid4()),
                "risk": "safe",
                "clause_number": "제1조",
                "original_text": "임대 목적물: 서울특별시 XX구 XX동 XX호",
                "explanation": "임대 목적물이 명확하게 명시되어 있습니다.",
                "law_reference": None,
                "recommendation": None,
            },
        ],
        "summary": {
            "high": 1,
            "medium": 1,
            "caution": 0,
            "safe": 1,
        },
        "special_clauses": [
            "임대인은 임차인의 서면 동의 없이 임대물의 구조를 변경할 수 없다.",
            "보증금은 계약 종료일에 즉시 반환한다.",
        ],
        "disclaimer": "본 분석은 법률 조언이 아닌 정보 제공 서비스입니다.",
    }
