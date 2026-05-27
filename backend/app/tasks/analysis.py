"""
Celery tasks for contract analysis.

This task orchestrates the analysis pipeline:
1. Update status to 'ocr'
2. Call AI pipeline (run_full_pipeline) — sync, runs in ThreadPoolExecutor
3. Convert pipeline result to DB format
4. Store result, update status to 'completed'

핵심 설계 원칙:
- asyncio.run()을 태스크당 단 한 번만 호출한다.
  (여러 번 호출하면 asyncpg 커넥션이 첫 번째 이벤트 루프에 묶여
   두 번째 호출부터 "attached to a different loop" 에러 발생)
- 동기 AI 파이프라인은 loop.run_in_executor()로 스레드에서 실행한다.
"""
import asyncio
import re
import uuid
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select

from app.tasks.celery_app import celery_app
from app.core.database import make_celery_session
from app.models.contract import Contract

logger = logging.getLogger(__name__)


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
            article = re.sub(r"^\((.+)\)$", r"\1", article).strip()
            return law_name, article

    return law_ref_str, ""


def _convert_pipeline_result(pipeline_result: dict, contract_id: str) -> dict:
    """
    ai.pipeline.run_full_pipeline() 반환값을 DB 저장 형식으로 변환한다.
    """
    raw_clauses = pipeline_result.get("clauses", [])
    converted_clauses = []

    for clause in raw_clauses:
        law_ref_str = clause.get("law_ref") or ""
        law_summary = clause.get("law_summary") or ""

        law_name, article = _parse_law_ref(law_ref_str)

        # placeholder / 불명확한 법령 참조는 제외
        _PLACEHOLDER_TERMS = {"관련 조항 확인 필요", "관련 조항 확인 권장", "법령 데이터베이스 확인 필요", "확인 권장"}
        _is_valid_law = (
            law_name in _KNOWN_LAW_NAMES
            and law_name not in _PLACEHOLDER_TERMS
            and article not in _PLACEHOLDER_TERMS
        )

        law_reference = None
        if _is_valid_law:
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
                "special_clause_draft": clause.get("special_clause_draft"),
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


# ─── 단일 async 컨텍스트로 전체 분석 실행 ──────────────────────────────────────

async def _run_analysis_coro(contract_id: str, job_id: str, s3_key: str) -> None:
    """
    전체 분석 파이프라인을 단일 asyncio 컨텍스트에서 실행한다.

    - DB 업데이트는 동일한 AsyncSession 재사용 → asyncpg 루프 충돌 없음
    - 동기 AI 파이프라인은 ThreadPoolExecutor 에서 실행 → 이벤트 루프 블로킹 없음
    """

    async def _update(
        db,
        status: str,
        progress: int,
        current_step: str,
        completed_steps: list,
        result: dict = None,
        error_code: str = None,
        error_message: str = None,
        report_id: str = None,
        ocr_text: str = None,
    ) -> None:
        res = await db.execute(
            select(Contract).where(Contract.job_id == uuid.UUID(job_id))
        )
        contract = res.scalar_one_or_none()
        if not contract:
            logger.error("[%s] Contract not found for job_id: %s", contract_id, job_id)
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
        logger.info("[%s] status → %s (%d%%)", contract_id, status, progress)

    async with make_celery_session()() as db:
        try:
            # ── Step 1: OCR 시작 ─────────────────────────────────────────────
            await _update(db, "ocr", 20, "ocr", ["upload"])

            # ── Step 2: 분석 중 ───────────────────────────────────────────────
            await _update(db, "analyzing", 50, "analyze", ["upload", "ocr"])

            # ── Step 3: AI 파이프라인 (동기 → 스레드풀) ──────────────────────
            from ai.pipeline import run_full_pipeline

            loop = asyncio.get_event_loop()
            logger.info("[%s] AI 파이프라인 시작 (s3_key=%s)", contract_id, s3_key)

            with ThreadPoolExecutor(max_workers=1) as executor:
                pipeline_result = await loop.run_in_executor(
                    executor,
                    lambda: run_full_pipeline(
                        contract_id=contract_id,
                        s3_key=s3_key,
                    ),
                )

            logger.info(
                "[%s] AI 파이프라인 완료 (status=%s, %.1fs)",
                contract_id,
                pipeline_result.get("status"),
                pipeline_result.get("elapsed_seconds", 0),
            )

            if pipeline_result.get("status") == "failed":
                raise RuntimeError(
                    pipeline_result.get("error") or "AI 파이프라인 실행 실패"
                )

            # ── Step 4: 결과 변환 ────────────────────────────────────────────
            db_result = _convert_pipeline_result(pipeline_result, contract_id)
            ocr_text = pipeline_result.get("raw_text", "")

            # ── Step 5: 특약 생성 중 ─────────────────────────────────────────
            await _update(db, "generating", 80, "clause", ["upload", "ocr", "analyze"])

            # ── Step 6: 완료 ─────────────────────────────────────────────────
            new_report_id = str(uuid.uuid4())
            await _update(
                db,
                "completed",
                100,
                "clause",
                ["upload", "ocr", "analyze", "clause"],
                result=db_result,
                report_id=new_report_id,
                ocr_text=ocr_text[:10_000] if ocr_text else None,
            )

        except Exception as exc:
            error_msg = str(exc)
            logger.error("[%s] 분석 실패: %s", contract_id, error_msg, exc_info=True)

            error_code = (
                "ANALYSIS_TIMEOUT" if "timeout" in error_msg.lower() else
                "OCR_FAILED" if "OCR" in error_msg.upper() else
                "INTERNAL_SERVER_ERROR"
            )

            try:
                await _update(
                    db,
                    "failed",
                    0,
                    "analyze",
                    [],
                    error_code=error_code,
                    error_message=error_msg[:500],  # DB 컬럼 크기 제한
                )
            except Exception as db_err:
                logger.error("[%s] failed 상태 업데이트 실패: %s", contract_id, db_err)

            raise


# ─── Celery Task ────────────────────────────────────────────────────────────

@celery_app.task(name="analysis.run_analysis", bind=True, max_retries=2)
def run_analysis_task(self, contract_id: str, job_id: str, s3_key: str):
    """
    계약서 AI 분석 Celery 태스크.

    asyncio.run()을 단 한 번 호출하여 asyncpg 이벤트 루프 충돌을 방지한다.
    """
    logger.info(
        "분석 태스크 시작 — contract_id=%s, job_id=%s",
        contract_id,
        job_id,
    )
    try:
        asyncio.run(_run_analysis_coro(contract_id, job_id, s3_key))
    except Exception as exc:
        # 일시적 오류 (네트워크, 타임아웃 등)에 대해서만 재시도
        if not isinstance(exc, (ValueError, TypeError, FileNotFoundError)):
            logger.warning(
                "[%s] 재시도 예약 (%d/%d): %s",
                contract_id,
                self.request.retries + 1,
                self.max_retries,
                exc,
            )
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
