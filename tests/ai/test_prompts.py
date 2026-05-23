"""
AI 프롬프트 빌더 함수 테스트

테스트 범위:
    - build_risk_analysis_prompt: 조항 분석용 프롬프트 생성
      - 법령 컨텍스트 있는 경우 (RAG 있음)
      - 법령 컨텍스트 없는 경우 (폴백)
    - build_search_query_prompt: 법령 검색 쿼리 생성
    - RISK_LEVEL_KOREAN: 위험도 한국어 매핑
"""
import pytest

# conftest.py에서 sys.path 설정됨 (root + backend 추가)
from backend.ai.prompts import (
    build_risk_analysis_prompt,
    build_search_query_prompt,
    RISK_LEVEL_KOREAN,
    SYSTEM_PROMPT,
)


# ─── RISK_LEVEL_KOREAN ────────────────────────────────────────────────────────

class TestRiskLevelKorean:

    def test_all_levels_present(self):
        assert "high" in RISK_LEVEL_KOREAN
        assert "medium" in RISK_LEVEL_KOREAN
        assert "caution" in RISK_LEVEL_KOREAN
        assert "safe" in RISK_LEVEL_KOREAN

    def test_korean_values_are_korean(self):
        for level, korean in RISK_LEVEL_KOREAN.items():
            # 한글 포함 여부 확인
            assert any('가' <= c <= '힣' for c in korean), \
                f"'{level}' 의 한국어 레이블이 한글을 포함하지 않음: {korean}"


# ─── SYSTEM_PROMPT ────────────────────────────────────────────────────────────

class TestSystemPrompt:

    def test_system_prompt_not_empty(self):
        assert len(SYSTEM_PROMPT.strip()) > 0

    def test_system_prompt_mentions_korea(self):
        assert "대한민국" in SYSTEM_PROMPT or "주택임대차" in SYSTEM_PROMPT

    def test_system_prompt_mentions_tenant(self):
        assert "임차인" in SYSTEM_PROMPT


# ─── build_risk_analysis_prompt ───────────────────────────────────────────────

class TestBuildRiskAnalysisPrompt:

    SAMPLE_CLAUSE = "수선 책임은 소모성 부품을 포함하여 임차인이 전부 부담한다."
    SAMPLE_LAW_CONTEXT = (
        "주택임대차보호법 제11조: 임차인은 임차물의 보존에 필요한 수선을 청구할 수 있으며, "
        "임대인은 임차물의 사용 및 수익에 필요한 상태를 유지하여야 한다."
    )

    def test_prompt_with_context_contains_clause(self):
        prompt = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="medium",
            law_context=self.SAMPLE_LAW_CONTEXT,
        )
        assert self.SAMPLE_CLAUSE in prompt

    def test_prompt_with_context_contains_law_context(self):
        prompt = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="medium",
            law_context=self.SAMPLE_LAW_CONTEXT,
        )
        assert self.SAMPLE_LAW_CONTEXT in prompt

    def test_prompt_with_context_contains_korean_risk_level(self):
        prompt = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="medium",
            law_context=self.SAMPLE_LAW_CONTEXT,
        )
        assert "중위험" in prompt  # medium의 한국어

    def test_prompt_with_context_contains_json_schema(self):
        prompt = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="medium",
            law_context=self.SAMPLE_LAW_CONTEXT,
        )
        assert "law_ref" in prompt
        assert "is_favorable" in prompt
        assert "explanation" in prompt
        assert "tenant_action" in prompt
        assert "severity_reason" in prompt

    def test_prompt_without_context_uses_fallback(self):
        """법령 컨텍스트 없으면 폴백 프롬프트를 사용한다."""
        prompt_no_ctx = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="caution",
            law_context="",
        )
        prompt_with_ctx = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="caution",
            law_context=self.SAMPLE_LAW_CONTEXT,
        )
        # 폴백 프롬프트에는 "데이터베이스를 사용할 수 없는" 문구가 있음
        assert "데이터베이스를 사용할 수 없는" in prompt_no_ctx
        assert "데이터베이스를 사용할 수 없는" not in prompt_with_ctx

    def test_prompt_without_context_contains_clause(self):
        prompt = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="caution",
            law_context="",
        )
        assert self.SAMPLE_CLAUSE in prompt

    def test_prompt_high_risk_uses_correct_korean(self):
        prompt = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="high",
            law_context=self.SAMPLE_LAW_CONTEXT,
        )
        assert "고위험" in prompt

    def test_prompt_caution_uses_correct_korean(self):
        prompt = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="caution",
            law_context="",
        )
        assert "주의" in prompt

    def test_prompt_safe_uses_correct_korean(self):
        prompt = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="safe",
            law_context="",
        )
        assert "정상" in prompt

    def test_prompt_whitespace_only_context_uses_fallback(self):
        """공백만 있는 컨텍스트도 폴백 처리한다."""
        prompt = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="medium",
            law_context="   \n   ",
        )
        assert "데이터베이스를 사용할 수 없는" in prompt

    def test_prompt_returns_string(self):
        result = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="medium",
            law_context=self.SAMPLE_LAW_CONTEXT,
        )
        assert isinstance(result, str)

    def test_prompt_unknown_risk_level_preserved(self):
        """알 수 없는 위험도는 그대로 표시된다."""
        prompt = build_risk_analysis_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="unknown_level",
            law_context="",
        )
        assert "unknown_level" in prompt


# ─── build_search_query_prompt ────────────────────────────────────────────────

class TestBuildSearchQueryPrompt:

    SAMPLE_CLAUSE = "보증금 반환 거절 시 연 12%의 이자를 가산한다."

    def test_returns_string(self):
        result = build_search_query_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="medium",
        )
        assert isinstance(result, str)

    def test_contains_clause_text(self):
        result = build_search_query_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="medium",
        )
        assert self.SAMPLE_CLAUSE[:50] in result

    def test_contains_korean_risk_level(self):
        result = build_search_query_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="medium",
        )
        assert "중위험" in result

    def test_long_clause_truncated_to_200_chars(self):
        long_clause = "아" * 300  # 300자 조항
        result = build_search_query_prompt(
            clause_text=long_clause,
            risk_level="caution",
        )
        # 200자까지만 포함되어야 함
        assert "아" * 200 in result
        assert "아" * 201 not in result

    def test_prompt_mentions_keywords(self):
        result = build_search_query_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="caution",
        )
        assert "키워드" in result

    def test_caution_risk_uses_correct_korean(self):
        result = build_search_query_prompt(
            clause_text=self.SAMPLE_CLAUSE,
            risk_level="caution",
        )
        assert "주의" in result
