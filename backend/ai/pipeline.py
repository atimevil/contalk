"""
AI 파이프라인 진입점 — 전체 분석 흐름을 조율한다.

흐름:
    S3 파일 다운로드
    → OCR (Google Vision API / pdfplumber 폴백)
    → 조항 파싱
    → KLUE-RoBERTa 위험도 분류 (rule-based 폴백)
    → RAG + GPT-4o 법령 근거 생성 (비정상 조항만)
    → AnalysisResult dict 반환

SLA: 1분 이내 처리 목표

백엔드(FastAPI/Celery)는 run_full_pipeline() 인터페이스만 호출한다.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 위험도별 처리 대상 (safe는 GPT-4o 호출 생략)
_RISK_LEVELS_TO_EXPLAIN = {"high", "medium", "caution"}

# 프론트엔드·DB 스키마 호환을 위한 표준 면책 문구
_DISCLAIMER = "본 분석은 법률 조언이 아닌 정보 제공 서비스입니다. 중요한 사항은 전문 법률가에게 확인하세요."


# ---------------------------------------------------------------------------
# 공개 인터페이스
# ---------------------------------------------------------------------------

def run_full_pipeline(contract_id: str, s3_key: str) -> dict:
    """
    임대차 계약서 전체 분석 파이프라인을 실행한다.

    Parameters
    ----------
    contract_id : str
        DB 계약서 레코드 ID (Contract.id). 로깅 및 결과 추적용.
    s3_key : str
        S3 오브젝트 키 (예: "contracts/uuid/filename.pdf")

    Returns
    -------
    dict  — AnalysisResult 형식 (backend Celery task가 DB에 저장)
        {
            "contract_id":    str,
            "status":         "completed" | "failed",
            "error":          str | None,
            "raw_text":       str,
            "ocr_confidence": float,
            "ocr_method":     str,           # "vision_api" | "pdfplumber" | "pytesseract"
            "total_clauses":  int,
            "risk_summary": {
                "high":    int,
                "medium":  int,
                "caution": int,
                "safe":    int,
            },
            "clauses": [
                {
                    "number":          str,   # 조항 번호 (예: "제1조", "특약사항")
                    "title":           str,   # 조항 제목 (있으면)
                    "text":            str,   # 조항 원문
                    "risk":            str,   # "high"|"medium"|"caution"|"safe"
                    "items":           list,  # 항(①②③) 목록
                    "law_ref":         str | None,
                    "law_summary":     str | None,
                    "explanation":     str | None,
                    "tenant_action":   str | None,
                    "severity_reason": str | None,
                },
            ],
            "special_clauses": list[str],    # 특약사항 텍스트 목록
            "disclaimer":      str,
            "elapsed_seconds": float,
        }
    """
    start_time = time.time()
    logger.info("[pipeline] contract_id=%s, s3_key=%s 분석 시작", contract_id, s3_key)

    result: Dict[str, Any] = {
        "contract_id": contract_id,
        "status": "failed",
        "error": None,
        "raw_text": "",
        "ocr_confidence": 0.0,
        "ocr_method": "",
        "total_clauses": 0,
        "risk_summary": {"high": 0, "medium": 0, "caution": 0, "safe": 0},
        "clauses": [],
        "special_clauses": [],
        "disclaimer": _DISCLAIMER,
        "elapsed_seconds": 0.0,
    }

    try:
        # ── Step 1: S3 다운로드 ──────────────────────────────────────────────
        logger.info("[Step 1] S3 파일 다운로드: %s", s3_key)
        file_bytes, content_type = _download_from_s3(s3_key)

        # ── Step 2: OCR ──────────────────────────────────────────────────────
        logger.info("[Step 2] OCR 처리 시작")
        from .ocr import run_ocr

        ocr_result = run_ocr(file_bytes, content_type)
        raw_text = ocr_result["raw_text"]

        if not raw_text.strip():
            raise RuntimeError("OCR 결과가 비어 있습니다. 파일을 확인하세요.")

        result["raw_text"] = raw_text
        result["ocr_confidence"] = ocr_result.get("confidence", 0.0)
        result["ocr_method"] = ocr_result.get("method", "unknown")
        logger.info(
            "[Step 2] OCR 완료: method=%s, confidence=%.2f, 텍스트 길이=%d자",
            result["ocr_method"],
            result["ocr_confidence"],
            len(raw_text),
        )

        # ── Step 3: 조항 파싱 ────────────────────────────────────────────────
        logger.info("[Step 3] 조항 파싱")
        from .clause_parser import parse_clauses

        clauses = parse_clauses(raw_text)
        logger.info("[Step 3] 조항 파싱 완료: %d개 조항", len(clauses))

        if not clauses:
            logger.warning("파싱된 조항이 없습니다. 원문을 단일 조항으로 처리합니다.")
            clauses = [{"number": "전문", "title": "", "text": raw_text[:2000], "items": []}]

        # ── Step 4: 위험도 분류 ───────────────────────────────────────────────
        logger.info("[Step 4] 위험도 분류 시작")
        from .classifier import classify_risk

        classified = classify_risk(clauses)
        logger.info("[Step 4] 분류 완료")

        # ── Step 5: RAG + GPT-4o (비정상 조항만) ─────────────────────────────
        logger.info("[Step 5] RAG 법령 근거 생성 시작")
        from .rag import explain_risk

        final_clauses: List[dict] = []
        risk_summary = {"high": 0, "medium": 0, "caution": 0, "safe": 0}
        special_clauses: List[str] = []

        for clause in classified:
            risk = clause.get("risk", "safe")
            risk_summary[risk] = risk_summary.get(risk, 0) + 1

            # 특약사항 수집
            if clause.get("number") == "특약사항":
                special_clauses.append(clause.get("text", ""))

            enriched = {**clause}

            if risk in _RISK_LEVELS_TO_EXPLAIN:
                logger.debug(
                    "[Step 5] 조항 %s (%s) RAG 분석 중...",
                    clause.get("number", "?"),
                    risk,
                )
                try:
                    rag_result = explain_risk(clause["text"], risk)
                    enriched["law_ref"] = rag_result.get("law_ref")
                    enriched["law_summary"] = rag_result.get("law_summary")
                    enriched["explanation"] = rag_result.get("explanation")
                    enriched["tenant_action"] = rag_result.get("tenant_action")
                    enriched["severity_reason"] = rag_result.get("severity_reason")
                except Exception as rag_exc:
                    logger.warning(
                        "조항 %s RAG 실패: %s", clause.get("number", "?"), rag_exc
                    )
                    enriched["law_ref"] = None
                    enriched["law_summary"] = None
                    enriched["explanation"] = "법령 근거 생성 중 오류가 발생했습니다."
                    enriched["tenant_action"] = None
                    enriched["severity_reason"] = None
            else:
                # safe 조항은 RAG 생략
                enriched["law_ref"] = None
                enriched["law_summary"] = None
                enriched["explanation"] = None
                enriched["tenant_action"] = None
                enriched["severity_reason"] = None

            final_clauses.append(enriched)

        elapsed = round(time.time() - start_time, 2)

        result.update(
            {
                "status": "completed",
                "error": None,
                "total_clauses": len(final_clauses),
                "risk_summary": risk_summary,
                "clauses": final_clauses,
                "special_clauses": special_clauses,
                "elapsed_seconds": elapsed,
            }
        )

        _log_summary(contract_id, risk_summary, elapsed)

        if elapsed > 60:
            logger.warning(
                "[pipeline] SLA 초과! 실제 소요: %.1f초 (목표: 60초). "
                "GPT-4o 호출 수: %d",
                elapsed,
                sum(1 for c in final_clauses if c.get("risk") in _RISK_LEVELS_TO_EXPLAIN),
            )

        return result

    except Exception as exc:
        elapsed = round(time.time() - start_time, 2)
        logger.error("[pipeline] contract_id=%s 분석 실패: %s", contract_id, exc, exc_info=True)
        result["status"] = "failed"
        result["error"] = str(exc)
        result["elapsed_seconds"] = elapsed
        return result


# ---------------------------------------------------------------------------
# S3 다운로드
# ---------------------------------------------------------------------------

def _download_from_s3(s3_key: str) -> tuple:
    """
    S3에서 파일을 다운로드하고 (bytes, content_type)을 반환한다.
    AWS 자격증명이 없으면 로컬 파일 경로로 폴백한다.
    """
    aws_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    aws_secret = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    bucket = os.environ.get("S3_BUCKET_NAME", "contalktok-contracts")

    if aws_key and aws_secret:
        return _s3_download(s3_key, bucket)
    else:
        logger.warning(
            "AWS 자격증명 미설정 — s3_key를 로컬 파일 경로로 해석합니다: %s", s3_key
        )
        return _local_file_read(s3_key)


def _s3_download(s3_key: str, bucket: str) -> tuple:
    """boto3를 사용하여 S3에서 파일을 다운로드한다."""
    try:
        import boto3  # type: ignore

        s3 = boto3.client(
            "s3",
            region_name=os.environ.get("AWS_REGION", "ap-northeast-2"),
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )

        response = s3.get_object(Bucket=bucket, Key=s3_key)
        file_bytes = response["Body"].read()
        content_type = response.get("ContentType", _guess_content_type(s3_key))

        logger.info(
            "S3 다운로드 완료: bucket=%s, key=%s, size=%d bytes",
            bucket, s3_key, len(file_bytes),
        )
        return file_bytes, content_type

    except ImportError:
        raise RuntimeError("boto3 패키지 미설치. pip install boto3")
    except Exception as exc:
        raise RuntimeError(f"S3 다운로드 실패 ({s3_key}): {exc}")


def _local_file_read(path: str) -> tuple:
    """로컬 파일을 읽는다 (개발/테스트 환경용)."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {path}")

    with open(path, "rb") as f:
        data = f.read()

    content_type = _guess_content_type(path)
    return data, content_type


def _guess_content_type(filename: str) -> str:
    """파일 확장자로 content_type을 추정한다."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        return "application/pdf"
    elif lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    elif lower.endswith(".png"):
        return "image/png"
    elif lower.endswith((".tiff", ".tif")):
        return "image/tiff"
    elif lower.endswith(".webp"):
        return "image/webp"
    else:
        return "application/octet-stream"


# ---------------------------------------------------------------------------
# 로깅 헬퍼
# ---------------------------------------------------------------------------

def _log_summary(contract_id: str, risk_summary: dict, elapsed: float) -> None:
    """분석 결과를 요약 로그로 출력한다."""
    total = sum(risk_summary.values())
    high = risk_summary.get("high", 0)
    medium = risk_summary.get("medium", 0)
    caution = risk_summary.get("caution", 0)
    normal = risk_summary.get("safe", 0)

    logger.info(
        "[pipeline] contract_id=%s 분석 완료 | "
        "소요: %.1f초 | 전체: %d조항 | "
        "고위험: %d, 중위험: %d, 주의: %d, 정상: %d",
        contract_id, elapsed, total, high, medium, caution, normal,
    )


# ---------------------------------------------------------------------------
# 독립 테스트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    import tempfile
    import io

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    print("=== 파이프라인 전체 독립 테스트 ===\n")
    print("AWS 자격증명 미설정 → 로컬 파일 경로로 동작\n")

    SAMPLE_CONTRACT = """주택 임대차 계약서

임대인: 홍길동
임차인: 김철수

제1조 (목적)
본 계약은 아래 부동산에 대한 임대차 계약을 체결함을 목적으로 한다.

제2조 (임대차 기간)
임대차 기간은 2024년 3월 1일부터 2026년 2월 28일까지 2년으로 한다.

제3조 (보증금 및 차임)
보증금은 금 일억원정(₩100,000,000)으로 하며, 계약금은 계약 시, 잔금은 입주일에 지불한다.

제4조 (임차인의 의무)
① 임차인은 임대인 동의 없이 목적물을 전대하거나 임차권을 양도할 수 없다.
② 수선 책임은 소모성 부품을 포함하여 임차인이 전부 부담한다.
③ 계약 종료 시 원상복구 의무를 진다.

특약사항
1. 보증금 반환 거절 시 연 12%의 이자를 가산한다.
2. 반려동물 사육 및 흡연은 금지한다.
"""

    # 임시 파일 생성
    try:
        from reportlab.pdfgen import canvas  # type: ignore
        from reportlab.lib.pagesizes import A4  # type: ignore

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        _, height = A4
        y = height - 50
        for line in SAMPLE_CONTRACT.split("\n"):
            c.drawString(40, y, line[:80])
            y -= 18
            if y < 50:
                c.showPage()
                y = height - 50
        c.save()

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(buf.getvalue())
            tmp_path = f.name

        print(f"테스트 PDF 생성: {tmp_path}\n")

    except ImportError:
        with tempfile.NamedTemporaryFile(
            suffix=".txt", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(SAMPLE_CONTRACT)
            tmp_path = f.name
        print(f"테스트 텍스트 파일 생성: {tmp_path}\n")

    result = run_full_pipeline(
        contract_id="test-contract-001",
        s3_key=tmp_path,
    )

    print(f"상태: {result['status']}")
    if result.get("error"):
        print(f"에러: {result['error']}")
    else:
        print(f"OCR 방법: {result['ocr_method']} (신뢰도: {result['ocr_confidence']})")
        print(f"전체 조항: {result['total_clauses']}개")
        print(f"위험도 요약: {result['risk_summary']}")
        print(f"소요 시간: {result['elapsed_seconds']}초\n")

        print("조항별 결과:")
        for clause in result["clauses"]:
            risk_emoji = {"high": "🔴", "medium": "🟠", "caution": "🟡", "safe": "✅"}.get(
                clause["risk"], "?"
            )
            print(
                f"  [{clause['number']}] {risk_emoji} {clause['risk']:8s} | "
                f"{clause['text'][:50]}..."
            )
            if clause.get("explanation"):
                print(f"    → {clause['explanation'][:80]}...")

    try:
        os.unlink(tmp_path)
    except Exception:
        pass

    print("\n파이프라인 테스트 완료.")
