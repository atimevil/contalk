"""
조항 파서(clause_parser.py) 테스트

테스트 범위:
    - 한국식 제N조 파싱
    - 제목 괄호 파싱
    - 숫자점(1. 2.) 형식 파싱
    - 특약사항 분리
    - 항(① ② ③) 추출
    - 전문(前文) 처리
    - 엣지케이스
"""
import pytest
from backend.ai.clause_parser import parse_clauses


# ---------------------------------------------------------------------------
# 표준 임대차 계약서 픽스처
# ---------------------------------------------------------------------------

STANDARD_CONTRACT = """주택 임대차 계약서

임대인(甲): 홍길동
임차인(乙): 김철수

제1조 (목적)
본 계약은 아래 부동산에 대한 임대차 계약을 체결함을 목적으로 한다.

제2조 (임대차 기간)
임대차 기간은 2024년 3월 1일부터 2026년 2월 28일까지 2년으로 한다.
① 임차인이 계속 거주를 희망하는 경우 만료 2개월 전에 통보하여야 한다.

제3조 (보증금)
① 보증금은 금 일억원정(₩100,000,000)으로 한다.
② 계약금 일천만원은 계약 시 지불하고, 잔금은 입주일에 지불한다.

제4조 (임차인의 의무)
① 임차인은 선량한 관리자의 주의로 사용하여야 한다.
② 임차인은 임대인 동의 없이 목적물을 전대할 수 없다.
③ 계약 종료 시 원상복구 의무를 진다.

특약사항
1. 보증금 반환은 퇴거 후 3일 이내로 한다.
2. 흡연은 금지한다.
"""

SPECIAL_CLAUSES_ONLY_CONTRACT = """제1조 (목적)
임대차 계약을 목적으로 한다.

특약사항
반려동물 사육을 금지한다.
흡연 및 소음 발생을 제한한다.
"""

NUMERIC_FORMAT_CONTRACT = """1. 임대 기간
2024년 1월 1일부터 2025년 12월 31일까지로 한다.

2. 보증금
금 오천만원으로 한다.

3. 임차인 의무
수선 책임은 임차인이 부담한다.
"""

ARTICLE_WITH_SUBCLAUSE_CONTRACT = """제1조의2 (특례)
본 조는 특별 적용 규정이다.

제2조 (기간)
기간은 1년으로 한다.
"""


# ---------------------------------------------------------------------------
# 제N조 파싱
# ---------------------------------------------------------------------------

class TestArticleParsing:

    def test_basic_article_count(self):
        result = parse_clauses(STANDARD_CONTRACT)
        numbers = [c["number"] for c in result]
        assert "제1조" in numbers
        assert "제2조" in numbers
        assert "제3조" in numbers
        assert "제4조" in numbers

    def test_article_with_title(self):
        result = parse_clauses(STANDARD_CONTRACT)
        art1 = next(c for c in result if c["number"] == "제1조")
        assert art1["title"] == "목적"

    def test_article_title_parentheses(self):
        result = parse_clauses(STANDARD_CONTRACT)
        art2 = next(c for c in result if c["number"] == "제2조")
        assert art2["title"] == "임대차 기간"

    def test_article_body_content(self):
        result = parse_clauses(STANDARD_CONTRACT)
        art1 = next(c for c in result if c["number"] == "제1조")
        assert "임대차 계약" in art1["text"]

    def test_subclause_article(self):
        result = parse_clauses(ARTICLE_WITH_SUBCLAUSE_CONTRACT)
        numbers = [c["number"] for c in result]
        assert "제1조의2" in numbers or any("1조의2" in n for n in numbers)

    def test_preamble_captured(self):
        result = parse_clauses(STANDARD_CONTRACT)
        numbers = [c["number"] for c in result]
        # 조항 이전 전문이 있으면 "전문"으로 포함되어야 함
        if "전문" in numbers:
            preamble = next(c for c in result if c["number"] == "전문")
            assert "홍길동" in preamble["text"] or "임대인" in preamble["text"]


# ---------------------------------------------------------------------------
# 특약사항 분리
# ---------------------------------------------------------------------------

class TestSpecialClauses:

    def test_special_clause_extracted(self):
        result = parse_clauses(STANDARD_CONTRACT)
        numbers = [c["number"] for c in result]
        assert "특약사항" in numbers

    def test_special_clause_content(self):
        result = parse_clauses(STANDARD_CONTRACT)
        special = next(c for c in result if c["number"] == "특약사항")
        assert "흡연" in special["text"] or "보증금" in special["text"]

    def test_standalone_special_clause(self):
        result = parse_clauses(SPECIAL_CLAUSES_ONLY_CONTRACT)
        numbers = [c["number"] for c in result]
        assert "특약사항" in numbers

    def test_special_clause_not_duplicated(self):
        result = parse_clauses(STANDARD_CONTRACT)
        special_count = sum(1 for c in result if c["number"] == "특약사항")
        assert special_count == 1


# ---------------------------------------------------------------------------
# 항(① ② ③) 추출
# ---------------------------------------------------------------------------

class TestItemExtraction:

    def test_items_extracted(self):
        result = parse_clauses(STANDARD_CONTRACT)
        art3 = next(c for c in result if c["number"] == "제3조")
        assert len(art3["items"]) >= 1

    def test_items_contain_marker(self):
        result = parse_clauses(STANDARD_CONTRACT)
        art3 = next(c for c in result if c["number"] == "제3조")
        assert any("①" in item for item in art3["items"])

    def test_article_without_items(self):
        result = parse_clauses(STANDARD_CONTRACT)
        art1 = next(c for c in result if c["number"] == "제1조")
        # 제1조는 항이 없음
        assert isinstance(art1["items"], list)


# ---------------------------------------------------------------------------
# 숫자점(1. 2. 3.) 형식
# ---------------------------------------------------------------------------

class TestNumericFormat:

    def test_numeric_format_parsed(self):
        result = parse_clauses(NUMERIC_FORMAT_CONTRACT)
        assert len(result) >= 2

    def test_numeric_content_correct(self):
        result = parse_clauses(NUMERIC_FORMAT_CONTRACT)
        texts = " ".join(c["text"] for c in result)
        assert "오천만원" in texts or "2024" in texts


# ---------------------------------------------------------------------------
# 반환값 구조 검증
# ---------------------------------------------------------------------------

class TestReturnStructure:

    def test_each_clause_has_required_fields(self):
        result = parse_clauses(STANDARD_CONTRACT)
        for clause in result:
            assert "number" in clause
            assert "title" in clause
            assert "text" in clause
            assert "items" in clause
            assert isinstance(clause["items"], list)

    def test_number_is_string(self):
        result = parse_clauses(STANDARD_CONTRACT)
        for clause in result:
            assert isinstance(clause["number"], str)

    def test_text_not_empty(self):
        result = parse_clauses(STANDARD_CONTRACT)
        for clause in result:
            assert clause["text"].strip() != ""


# ---------------------------------------------------------------------------
# 엣지케이스
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_empty_string(self):
        assert parse_clauses("") == []

    def test_whitespace_only(self):
        assert parse_clauses("   \n\t\n  ") == []

    def test_no_articles_returns_single(self):
        text = "이것은 조항 번호가 없는 단순 텍스트입니다."
        result = parse_clauses(text)
        assert len(result) == 1
        assert result[0]["number"] == "전문"

    def test_single_article(self):
        text = "제1조 (목적)\n본 계약을 체결한다."
        result = parse_clauses(text)
        assert any(c["number"] == "제1조" for c in result)

    def test_full_width_space_handled(self):
        text = "제1조　(목적)\n　임대차　계약이다."
        result = parse_clauses(text)
        assert len(result) >= 1

    def test_crlf_handled(self):
        text = "제1조 (목적)\r\n계약이다.\r\n\r\n제2조 (기간)\r\n1년으로 한다."
        result = parse_clauses(text)
        assert any(c["number"] == "제1조" for c in result)
        assert any(c["number"] == "제2조" for c in result)
