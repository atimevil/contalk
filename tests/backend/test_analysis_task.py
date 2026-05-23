"""
Celery 분석 태스크 — 결과 변환 함수 테스트

테스트 범위:
    - _parse_law_ref: 법령 문자열 파싱
    - _convert_pipeline_result: 파이프라인 → DB 형식 변환
    - 엣지케이스: None 값, 빈 리스트, 실패 상태
"""
import uuid
import pytest
from backend.app.tasks.analysis import _parse_law_ref, _convert_pipeline_result


# ─── 공통 픽스처 ──────────────────────────────────────────────────────────────

@pytest.fixture
def full_pipeline_output():
    return {
        "status": "completed",
        "raw_text": "주택 임대차 계약서 텍스트",
        "ocr_method": "plain_text",
        "ocr_confidence": 1.0,
        "total_clauses": 3,
        "risk_summary": {"high": 0, "medium": 1, "caution": 1, "safe": 1},
        "clauses": [
            {
                "number": "제4조",
                "title": "임차인의 의무",
                "text": "수선 책임은 소모성 부품을 포함하여 임차인이 전부 부담한다.",
                "risk": "medium",
                "items": [],
                "law_ref": "주택임대차보호법 제11조",
                "law_summary": "임차인은 임차물을 선량한 관리자의 주의로 보존하여야 한다.",
                "is_favorable": False,
                "explanation": "임차인에게 불리한 조항입니다.",
                "tenant_action": "수선비 부담 범위를 협의하세요.",
                "severity_reason": "수선 책임 전가 조항",
            },
            {
                "number": "특약사항",
                "title": "",
                "text": "보증금 반환 거절 시 연 12%의 이자를 가산한다.",
                "risk": "caution",
                "items": [],
                "law_ref": "주택임대차보호법 관련 조항",
                "law_summary": "보증금 반환 지연 시 이자",
                "is_favorable": True,
                "explanation": "임차인에게 유리한 조항입니다.",
                "tenant_action": "이자 지급 요구 가능",
                "severity_reason": "임차인 보호 조항",
            },
            {
                "number": "제1조",
                "title": "목적",
                "text": "본 계약은 임대차 계약을 체결함을 목적으로 한다.",
                "risk": "safe",
                "items": [],
                "law_ref": None,
                "law_summary": None,
                "is_favorable": None,
                "explanation": None,
                "tenant_action": None,
                "severity_reason": None,
            },
        ],
        "special_clauses": ["보증금 반환 거절 시 연 12%의 이자를 가산한다."],
        "disclaimer": "본 분석은 법률 조언이 아닌 정보 제공 서비스입니다.",
        "elapsed_seconds": 12.5,
    }


# ─── _parse_law_ref 테스트 ─────────────────────────────────────────────────────

class TestParseLawRef:

    def test_full_reference_parsed(self):
        law, article = _parse_law_ref("주택임대차보호법 제3조 제1항")
        assert law == "주택임대차보호법"
        assert article == "제3조 제1항"

    def test_civil_law_parsed(self):
        law, article = _parse_law_ref("민법 제623조")
        assert law == "민법"
        assert article == "제623조"

    def test_commercial_lease_law_parsed(self):
        law, article = _parse_law_ref("상가건물 임대차보호법 제10조")
        assert law == "상가건물 임대차보호법"
        assert article == "제10조"

    def test_parentheses_note_cleaned(self):
        law, article = _parse_law_ref("주택임대차보호법 (관련 조항 확인 권장)")
        assert law == "주택임대차보호법"
        assert article == "관련 조항 확인 권장"

    def test_empty_string_returns_empty(self):
        law, article = _parse_law_ref("")
        assert law == ""
        assert article == ""

    def test_none_like_dummy_string(self):
        law, article = _parse_law_ref("OPENAI_API_KEY 설정 후 정확한 조항 제공")
        # 알려진 법령명이 아니므로 전체가 law_name으로
        assert article == ""

    def test_law_name_only_no_article(self):
        law, article = _parse_law_ref("주택임대차보호법")
        assert law == "주택임대차보호법"
        assert article == ""


# ─── _convert_pipeline_result 테스트 ─────────────────────────────────────────

class TestConvertPipelineResult:

    def test_contract_id_preserved(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "my-contract-123")
        assert result["contract_id"] == "my-contract-123"

    def test_summary_keys_correct(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        assert set(result["summary"].keys()) == {"high", "medium", "caution", "safe"}

    def test_summary_values_correct(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        assert result["summary"]["medium"] == 1
        assert result["summary"]["caution"] == 1
        assert result["summary"]["safe"] == 1
        assert result["summary"]["high"] == 0

    def test_clause_count_matches(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        assert len(result["clauses"]) == 3

    def test_clause_number_mapped(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        numbers = [c["clause_number"] for c in result["clauses"]]
        assert "제4조" in numbers
        assert "특약사항" in numbers
        assert "제1조" in numbers

    def test_clause_text_mapped_to_original_text(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "제4조")
        assert "수선 책임" in clause["original_text"]

    def test_medium_clause_has_law_reference(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "제4조")
        assert clause["law_reference"] is not None
        assert clause["law_reference"]["law_name"] == "주택임대차보호법"
        assert clause["law_reference"]["article"] == "제11조"

    def test_safe_clause_has_no_law_reference(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "제1조")
        assert clause["law_reference"] is None

    def test_is_favorable_false_for_medium(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "제4조")
        assert clause["is_favorable"] is False

    def test_is_favorable_true_for_caution_beneficial(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "특약사항")
        assert clause["is_favorable"] is True

    def test_is_favorable_none_for_safe(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "제1조")
        assert clause["is_favorable"] is None

    def test_recommendation_from_tenant_action(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "제4조")
        assert clause["recommendation"] == "수선비 부담 범위를 협의하세요."

    def test_special_clauses_list_preserved(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        assert isinstance(result["special_clauses"], list)
        assert len(result["special_clauses"]) == 1

    def test_disclaimer_preserved(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        assert "법률 조언" in result["disclaimer"]

    def test_clause_ids_are_unique_uuids(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        ids = [c["id"] for c in result["clauses"]]
        assert len(ids) == len(set(ids))  # 중복 없음
        for id_str in ids:
            uuid.UUID(id_str)  # 유효한 UUID 형식

    def test_ocr_method_preserved(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        assert result["ocr_method"] == "plain_text"

    def test_ocr_confidence_preserved(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        assert result["ocr_confidence"] == 1.0

    def test_empty_clauses_list(self):
        pipeline_out = {
            "status": "completed",
            "risk_summary": {"high": 0, "medium": 0, "caution": 0, "safe": 0},
            "clauses": [],
            "special_clauses": [],
            "disclaimer": "안내문",
            "ocr_method": "mock",
            "ocr_confidence": 0.0,
            "elapsed_seconds": 0.5,
        }
        result = _convert_pipeline_result(pipeline_out, "empty")
        assert result["clauses"] == []
        assert result["summary"]["safe"] == 0

    def test_law_reference_url_is_none(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "제4조")
        assert clause["law_reference"]["url"] is None

    def test_law_summary_in_law_reference(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "제4조")
        assert "보존" in clause["law_reference"]["summary"]

    def test_severity_reason_preserved(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "제4조")
        assert clause["severity_reason"] == "수선 책임 전가 조항"

    def test_explanation_preserved(self, full_pipeline_output):
        result = _convert_pipeline_result(full_pipeline_output, "test")
        clause = next(c for c in result["clauses"] if c["clause_number"] == "제4조")
        assert "불리" in clause["explanation"]
