"""
AI 파이프라인 통합 테스트 — S3/OCR 모킹 후 분류~결과 반환까지 검증

테스트 범위:
    - 전체 파이프라인 실행 (로컬 텍스트 파일)
    - 반환값 구조 검증
    - 위험도 요약 정확성
    - 특약사항 수집
    - 에러 처리
    - SLA(60초) 기록 여부
"""
import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from backend.ai.pipeline import run_full_pipeline


# ---------------------------------------------------------------------------
# 테스트용 계약서 텍스트
# ---------------------------------------------------------------------------

# 위험 조항이 없는 정상 계약서
SAFE_CONTRACT = """주택 임대차 계약서

임대인: 홍길동
임차인: 김철수

제1조 (목적)
본 계약은 서울시 강남구 역삼동 123-45 소재 아파트에 대한 임대차 계약을 목적으로 한다.

제2조 (임대차 기간)
임대차 기간은 2024년 3월 1일부터 2026년 2월 28일까지 2년으로 한다.
① 임차인이 계속 거주를 원하는 경우 만료 2개월 전에 임대인에게 통보한다.

제3조 (보증금)
① 보증금은 금 일억원정(₩100,000,000)으로 한다.
② 계약금 일천만원은 계약 시, 잔금은 입주일에 지불한다.

제4조 (임대인의 의무)
임대인은 임차인이 목적물을 사용·수익할 수 있도록 유지하여야 한다.
"""

# 위험 조항이 있는 불리한 계약서
RISKY_CONTRACT = """주택 임대차 계약서

임대인: 홍길동
임차인: 김철수

제1조 (목적)
본 계약은 아래 부동산에 대한 임대차 계약을 체결함을 목적으로 한다.

제2조 (임대차 기간)
임대차 기간은 2024년 3월 1일부터 2025년 2월 28일까지로 한다.

제3조 (임차인의 의무)
① 수선 책임은 소모성 부품을 포함하여 임차인이 전부 부담한다.
② 계약 종료 시 원상복구 의무를 진다.
③ 임대인이 언제든지 해지할 수 있다.

제4조 (금지사항)
흡연 금지, 반려동물 금지.

특약사항
1. 보증금 반환 거절 시 임차인은 이의를 제기할 수 없다.
2. 확정일자 신청 금지.
"""

# 특약사항만 문제 있는 계약서
MIXED_CONTRACT = """주택 임대차 계약서

제1조 (목적)
본 계약은 임대차를 목적으로 한다.

제2조 (기간)
임대차 기간은 2024년부터 2026년까지 2년으로 한다.

제3조 (보증금)
보증금은 금 오천만원으로 한다.

특약사항
전대 금지, 에어컨 설치 금지.
"""


# ---------------------------------------------------------------------------
# 픽스처: 로컬 파일 기반 파이프라인 실행 헬퍼
# ---------------------------------------------------------------------------

def run_pipeline_with_text(contract_text: str) -> dict:
    """텍스트를 임시 파일로 저장 후 파이프라인 실행."""
    with tempfile.NamedTemporaryFile(
        suffix=".txt", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(contract_text)
        tmp_path = f.name

    try:
        # OCR을 건너뛰고 텍스트를 직접 주입하기 위해 run_ocr를 모킹
        mock_ocr_result = {
            "raw_text": contract_text,
            "confidence": 1.0,
            "method": "mock",
        }
        with patch("backend.ai.pipeline._download_from_s3") as mock_dl, \
             patch("backend.ai.ocr.run_ocr") as mock_ocr, \
             patch("backend.ai.rag.explain_risk") as mock_rag:

            mock_dl.return_value = (contract_text.encode("utf-8"), "text/plain")
            mock_ocr.return_value = mock_ocr_result
            mock_rag.return_value = {
                "law_ref": "주택임대차보호법 제3조",
                "law_summary": "임차인 보호 조항",
                "explanation": "해당 조항은 임차인에게 불리합니다.",
                "tenant_action": "법률 전문가 상담 권장",
                "severity_reason": "임차인 권리 침해 가능성",
            }

            return run_full_pipeline(
                contract_id="test-001",
                s3_key=tmp_path,
            )
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 반환값 구조 검증
# ---------------------------------------------------------------------------

class TestPipelineReturnStructure:

    def test_status_completed(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        assert result["status"] == "completed"

    def test_required_keys_present(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        required = [
            "contract_id", "status", "error", "raw_text",
            "ocr_confidence", "ocr_method", "total_clauses",
            "risk_summary", "clauses", "special_clauses",
            "disclaimer", "elapsed_seconds",
        ]
        for key in required:
            assert key in result, f"키 누락: {key}"

    def test_contract_id_preserved(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        assert result["contract_id"] == "test-001"

    def test_risk_summary_keys(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        assert "medium" in result["risk_summary"]
        assert "caution" in result["risk_summary"]
        assert "safe" in result["risk_summary"]

    def test_risk_summary_sum_equals_total(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        summary_total = sum(result["risk_summary"].values())
        assert summary_total == result["total_clauses"]

    def test_clauses_is_list(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        assert isinstance(result["clauses"], list)

    def test_each_clause_has_risk_field(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        for clause in result["clauses"]:
            assert "risk" in clause
            assert clause["risk"] in {"medium", "caution", "safe"}

    def test_disclaimer_present(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        assert result["disclaimer"]
        assert len(result["disclaimer"]) > 10

    def test_elapsed_seconds_positive(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        assert result["elapsed_seconds"] >= 0


# ---------------------------------------------------------------------------
# 위험도 분류 정확성
# ---------------------------------------------------------------------------

class TestRiskClassificationAccuracy:

    def test_safe_contract_mostly_safe(self):
        result = run_pipeline_with_text(SAFE_CONTRACT)
        safe_count = result["risk_summary"].get("safe", 0)
        total = result["total_clauses"]
        assert safe_count / total >= 0.5, f"정상 계약서에서 safe 비율 낮음: {safe_count}/{total}"

    def test_risky_contract_has_medium(self):
        result = run_pipeline_with_text(RISKY_CONTRACT)
        assert result["risk_summary"].get("medium", 0) > 0

    def test_risky_contract_has_caution(self):
        result = run_pipeline_with_text(RISKY_CONTRACT)
        assert result["risk_summary"].get("caution", 0) > 0

    def test_mixed_contract_has_caution(self):
        result = run_pipeline_with_text(MIXED_CONTRACT)
        assert result["risk_summary"].get("caution", 0) > 0

    def test_risky_clause_has_explanation(self):
        result = run_pipeline_with_text(RISKY_CONTRACT)
        risky = [c for c in result["clauses"] if c["risk"] in {"medium", "caution"}]
        assert len(risky) > 0
        # 위험 조항에는 explanation이 있어야 함 (RAG 모킹)
        for clause in risky:
            assert "explanation" in clause


# ---------------------------------------------------------------------------
# 특약사항 수집
# ---------------------------------------------------------------------------

class TestSpecialClauses:

    def test_special_clauses_collected(self):
        result = run_pipeline_with_text(RISKY_CONTRACT)
        assert isinstance(result["special_clauses"], list)
        assert len(result["special_clauses"]) > 0

    def test_special_clause_text_not_empty(self):
        result = run_pipeline_with_text(RISKY_CONTRACT)
        for text in result["special_clauses"]:
            assert text.strip() != ""

    def test_no_special_clauses_if_absent(self):
        contract_no_special = """제1조 (목적)
임대차 계약을 목적으로 한다.

제2조 (기간)
2년으로 한다.
"""
        result = run_pipeline_with_text(contract_no_special)
        assert result["special_clauses"] == []


# ---------------------------------------------------------------------------
# 에러 처리
# ---------------------------------------------------------------------------

class TestErrorHandling:

    def test_file_not_found_returns_failed(self):
        with patch("backend.ai.pipeline._download_from_s3") as mock_dl:
            mock_dl.side_effect = FileNotFoundError("파일 없음")
            result = run_full_pipeline(
                contract_id="err-001",
                s3_key="nonexistent/path.pdf",
            )
        assert result["status"] == "failed"
        assert result["error"] is not None
        assert result["contract_id"] == "err-001"

    def test_empty_ocr_result_returns_failed(self):
        with patch("backend.ai.pipeline._download_from_s3") as mock_dl, \
             patch("backend.ai.ocr.run_ocr") as mock_ocr:
            mock_dl.return_value = (b"", "text/plain")
            mock_ocr.return_value = {"raw_text": "", "confidence": 0.0, "method": "mock"}
            result = run_full_pipeline(
                contract_id="err-002",
                s3_key="empty.pdf",
            )
        assert result["status"] == "failed"

    def test_rag_failure_doesnt_crash_pipeline(self):
        """RAG 실패해도 파이프라인은 완료 상태로 반환되어야 함."""
        with patch("backend.ai.pipeline._download_from_s3") as mock_dl, \
             patch("backend.ai.ocr.run_ocr") as mock_ocr, \
             patch("backend.ai.rag.explain_risk") as mock_rag:
            mock_dl.return_value = (RISKY_CONTRACT.encode("utf-8"), "text/plain")
            mock_ocr.return_value = {
                "raw_text": RISKY_CONTRACT,
                "confidence": 1.0,
                "method": "mock",
            }
            mock_rag.side_effect = RuntimeError("RAG 서버 다운")
            result = run_full_pipeline(
                contract_id="rag-fail-001",
                s3_key="test.pdf",
            )
        assert result["status"] == "completed"
        risky = [c for c in result["clauses"] if c["risk"] in {"medium", "caution"}]
        for clause in risky:
            assert clause.get("explanation") is not None


# ---------------------------------------------------------------------------
# 실제 계약서 시나리오 (통합 시나리오)
# ---------------------------------------------------------------------------

REAL_WORLD_CONTRACT = """주택 임대차 계약서

본 계약서는 임대인(이하 "갑")과 임차인(이하 "을") 간에 아래와 같이 체결한다.

제1조 (임대 목적물)
소재지: 서울특별시 마포구 합정동 123-45, 전용면적 59㎡ 아파트

제2조 (임대차 기간)
임대차 기간은 2024년 6월 1일부터 2026년 5월 31일까지 24개월로 한다.

제3조 (보증금 및 차임)
① 보증금은 금 이억원정(₩200,000,000)으로 한다.
② 월 차임은 없는 전세 계약으로 한다.

제4조 (인도 및 명도)
갑은 을에게 2024년 6월 1일까지 목적물을 인도하여야 한다.

제5조 (임차인의 의무)
① 을은 선량한 관리자의 주의로 목적물을 사용하여야 한다.
② 을은 갑의 서면 동의 없이 목적물을 전대하거나 임차권을 양도할 수 없다.
③ 계약 종료 시 원상복구 의무를 진다.
④ 수선 책임은 소모성 부품에 한하여 을이 부담한다.

제6조 (임대인의 의무)
갑은 을이 목적물을 사용·수익할 수 있는 상태로 유지하여야 한다.

제7조 (금지사항)
반려동물 사육 및 흡연은 금지한다.

제8조 (계약 해지)
① 을이 2기 이상 차임을 연체한 경우 갑은 계약을 해지할 수 있다.
② 갑이 목적물을 매도할 경우 을에게 사전 통보하여야 한다.

특약사항
1. 보증금 반환은 을의 퇴거 확인 후 3영업일 이내로 한다.
2. 확정일자 신청 금지 및 임차권 등기 신청 금지.
3. 임대인은 언제든지 방문·출입할 수 있다.
"""


# ---------------------------------------------------------------------------
# 계약 유형 자동 감지
# ---------------------------------------------------------------------------

# 표준 양식의 "차임(월세)" 라벨은 있으나 실제로는 전세인 계약서
# (개선 전 로직은 "월세" 단어만 보고 monthly로 오분류했음)
JEONSE_WITH_LABEL_CONTRACT = """주택 임대차 계약서

제3조 (보증금 및 차임)
① 전세보증금은 금 삼억원정(300,000,000원)으로 한다.
② 차임(월세): 해당 없음 (전세 계약)
"""

# 실제 월세 금액이 명시된 월세 계약서
MONTHLY_CONTRACT = """주택 임대차 계약서

제3조 (보증금 및 차임)
① 보증금은 금 일천만원(10,000,000원)으로 한다.
② 월세는 매월 500,000원으로 한다.
"""


class TestContractTypeDetection:

    def test_real_world_detected_as_jeonse(self):
        result = run_pipeline_with_text(REAL_WORLD_CONTRACT)
        assert result["contract_type"] == "jeonse"

    def test_monthly_with_amount_detected(self):
        result = run_pipeline_with_text(MONTHLY_CONTRACT)
        assert result["contract_type"] == "monthly"

    def test_jeonse_label_not_misdetected_as_monthly(self):
        """'차임(월세)' 라벨이 있어도 금액이 없고 전세면 jeonse로 판정해야 함."""
        result = run_pipeline_with_text(JEONSE_WITH_LABEL_CONTRACT)
        assert result["contract_type"] == "jeonse"

    def test_unknown_when_no_signal(self):
        contract = """제1조 (목적)
임대차 계약을 목적으로 한다.

제2조 (기간)
2년으로 한다.
"""
        result = run_pipeline_with_text(contract)
        assert result["contract_type"] == "unknown"


class TestRealWorldScenario:

    def test_real_contract_completes(self):
        result = run_pipeline_with_text(REAL_WORLD_CONTRACT)
        assert result["status"] == "completed"

    def test_real_contract_clause_count(self):
        result = run_pipeline_with_text(REAL_WORLD_CONTRACT)
        assert result["total_clauses"] >= 5

    def test_real_contract_has_special_clauses(self):
        result = run_pipeline_with_text(REAL_WORLD_CONTRACT)
        assert len(result["special_clauses"]) > 0

    def test_real_contract_detects_medium_risks(self):
        result = run_pipeline_with_text(REAL_WORLD_CONTRACT)
        # 특약사항에 확정일자 금지, 임차권 등기 금지, 임대인 언제든지 방문 → medium
        assert result["risk_summary"].get("medium", 0) > 0

    def test_real_contract_detects_caution_risks(self):
        result = run_pipeline_with_text(REAL_WORLD_CONTRACT)
        # 반려동물 금지, 흡연 금지 → caution
        assert result["risk_summary"].get("caution", 0) > 0

    def test_real_contract_json_serializable(self):
        result = run_pipeline_with_text(REAL_WORLD_CONTRACT)
        # FastAPI가 JSON으로 직렬화 가능해야 함
        serialized = json.dumps(result, ensure_ascii=False)
        assert len(serialized) > 0
