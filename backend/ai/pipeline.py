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
import re
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
        "contract_type": "unknown",
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

        # ── Step 2.5: 계약 유형 자동 감지 ────────────────────────────────────
        contract_type = _detect_contract_type(raw_text)
        result["contract_type"] = contract_type
        logger.info("[Step 2.5] 계약 유형 감지: %s", contract_type)

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

        # ── Step 5: RAG + GPT-4o (비정상 조항만) — 병렬 처리 ──────────────────
        logger.info("[Step 5] RAG 법령 근거 생성 시작 (병렬)")
        from .rag import explain_risk
        from concurrent.futures import ThreadPoolExecutor, as_completed

        final_clauses: List[dict] = []
        risk_summary = {"high": 0, "medium": 0, "caution": 0, "safe": 0}
        special_clauses: List[str] = []

        # 특약사항 수집 + risk_summary 집계
        # clause_parser가 특약 블록을 "특약사항"/"특약 1"/"특약 2"...로 분리하므로
        # 번호가 "특약"으로 시작하는 조항을 모두 수집한다.
        for clause in classified:
            risk = clause.get("risk", "safe")
            risk_summary[risk] = risk_summary.get(risk, 0) + 1
            if clause.get("number", "").startswith("특약"):
                special_clauses.append(clause.get("text", ""))

        # RAG 필요 조항 / 불필요 조항 분리
        to_explain = [(i, c) for i, c in enumerate(classified) if c.get("risk") in _RISK_LEVELS_TO_EXPLAIN]
        no_explain = [(i, c) for i, c in enumerate(classified) if c.get("risk") not in _RISK_LEVELS_TO_EXPLAIN]

        # 병렬 RAG 호출 (max_workers=5 — OpenAI rate limit 안전 마진)
        enriched_map: dict[int, dict] = {}

        def _run_rag(idx_clause):
            idx, clause = idx_clause
            try:
                rag_result = explain_risk(clause["text"], clause.get("risk", "medium"))
                return idx, {**clause, **{
                    "law_ref": rag_result.get("law_ref"),
                    "law_summary": rag_result.get("law_summary"),
                    "is_favorable": rag_result.get("is_favorable"),
                    "explanation": rag_result.get("explanation"),
                    "tenant_action": rag_result.get("tenant_action"),
                    "severity_reason": rag_result.get("severity_reason"),
                    "special_clause_draft": rag_result.get("special_clause_draft"),
                }}
            except Exception as rag_exc:
                logger.warning("조항 %s RAG 실패: %s", clause.get("number", "?"), rag_exc)
                return idx, {**clause, **{
                    "law_ref": None, "law_summary": None, "is_favorable": None,
                    "explanation": "법령 근거 생성 중 오류가 발생했습니다.",
                    "tenant_action": None, "severity_reason": None, "special_clause_draft": None,
                }}

        if to_explain:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(_run_rag, item): item[0] for item in to_explain}
                for future in as_completed(futures):
                    idx, enriched = future.result()
                    enriched_map[idx] = enriched

        # safe 조항 처리 (RAG 생략)
        for idx, clause in no_explain:
            enriched_map[idx] = {**clause, **{
                "law_ref": None, "law_summary": None, "is_favorable": None,
                "explanation": None, "tenant_action": None,
                "severity_reason": None, "special_clause_draft": None,
            }}

        # 원래 순서 복원
        final_clauses = [enriched_map[i] for i in range(len(classified))]

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
# 계약 유형 감지
# ---------------------------------------------------------------------------

# 금액 패턴: ₩300,000 / 500,000원 / 50만원 등 (단위 필수로 오탐 억제)
_AMOUNT_RE = re.compile(r"(?:₩\s*)?([0-9][0-9,]{0,15})\s*(만원|원)")

# 한글 수사 금액 패턴 (예: "팔십만원", "오천만원정") — 차임을 한글로만 적은 계약서 대응
_KO_AMOUNT_RE = re.compile(r"([일이삼사오육칠팔구십백천만억]+)\s*원")
_KO_DIGIT = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
_KO_SMALL = {"십": 10, "백": 100, "천": 1000}
_KO_BIG = {"만": 10_000, "억": 100_000_000}


def _korean_amount_to_int(s: str) -> int:
    """한글 수사 금액을 정수로 변환한다. 예: '팔십만' → 800000, '오천만' → 50000000."""
    total = section = num = 0
    for ch in s:
        if ch in _KO_DIGIT:
            num = _KO_DIGIT[ch]
        elif ch in _KO_SMALL:
            section += (num or 1) * _KO_SMALL[ch]
            num = 0
        elif ch in _KO_BIG:
            section += num
            total += section * _KO_BIG[ch]
            section = num = 0
    return total + section + num


def _extract_amount_near(text: str, keywords: tuple, window: int = 20) -> Optional[int]:
    """
    키워드 등장 직후 window 글자 내에서 첫 금액(원 단위)을 추출한다.
    찾지 못하면 None (금액이 명시되지 않음).

    키워드와 금액 사이에 "보증금"/"전세"가 끼면 그 금액은 보증금/전세금이므로
    무시한다 — 예: 제목 "(보증금 및 차임)" 뒤에 오는 전세보증금 금액 오탐 방지.

    예) "월세는 매월 500,000원" → 500000 / "차임 50만원" → 500000
    """
    for kw in keywords:
        idx = text.find(kw)
        while idx != -1:
            segment = text[idx + len(kw): idx + len(kw) + window]
            if not any(x in segment for x in ("보증금", "전세")):
                m = _AMOUNT_RE.search(segment)
                if m:
                    num = int(m.group(1).replace(",", ""))
                    return num * 10_000 if m.group(2) == "만원" else num
                # 아라비아 금액이 없으면 한글 수사 금액("팔십만원")을 시도
                km = _KO_AMOUNT_RE.search(segment)
                if km:
                    val = _korean_amount_to_int(km.group(1))
                    if val > 0:
                        return val
            idx = text.find(kw, idx + 1)
    return None


def _detect_contract_type(text: str) -> str:
    """
    OCR 텍스트에서 임대차 계약 유형을 감지한다.

    판단 우선순위:
    1. "월세"/"차임" 근처에 0원 초과 금액이 있으면 → "monthly"
       (전세+월세 혼용 시에도 실제 월세 금액이 있으면 월세 계약으로 봄)
    2. "전세"/"전세금"/"전세보증금" 키워드가 있으면 → "jeonse"
    3. 월 차임 금액이 없고 보증금만 있으면 → "jeonse"
       ("차임" 단어는 전세 계약 표준 조항에도 등장하므로 단어만으로 월세 판정 안 함)
    4. 보증금도 없이 월세/차임 언급만 있으면 → "monthly"
    5. 판단 불가 → "unknown"

    표준임대차계약서 양식에는 "차임(월세)" 라벨이 인쇄돼 있어,
    단순 "월세" 키워드 매칭은 전세 계약을 월세로 오분류한다.
    따라서 키워드 근처의 실제 금액을 우선 판단 근거로 사용한다.
    """
    norm = re.sub(r"\s+", " ", text)

    # 1. 월세/차임 금액이 실제로 0보다 크면 월세 계약
    rent = _extract_amount_near(norm, ("월세", "차임"))
    if rent is not None and rent > 0:
        return "monthly"

    # 2. 전세 키워드가 있으면 전세 (양식의 "월세" 라벨에 속지 않음)
    if any(kw in norm for kw in ("전세", "전세금", "전세보증금")):
        return "jeonse"

    # 3. 보증금만 있고 월 차임 금액이 없으면 전세로 추정한다.
    #    "차임" 단어(예: "2기 차임 연체 시 해지")는 표준 전세 계약에도 등장하므로
    #    단어 존재만으로 월세 판정하지 않는다 — 신뢰 신호는 실제 차임 금액(step 1).
    if "보증금" in norm:
        return "jeonse"

    # 4. 보증금조차 없지만 월세/차임 언급만 있으면 월세로 추정
    if "월세" in norm or "차임" in norm:
        return "monthly"

    return "unknown"


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

    # 임시 텍스트 파일 생성 (reportlab은 한국어 폰트 미등록 시 글자 깨짐)
    with tempfile.NamedTemporaryFile(
        suffix=".txt", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(SAMPLE_CONTRACT)
        tmp_path = f.name

    print(f"테스트 파일 생성: {tmp_path}\n")

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
            risk_emoji = {"medium": "🟠", "caution": "🟡", "safe": "✅"}.get(
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
