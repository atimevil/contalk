"""
GPT-4o 프롬프트 템플릿 모음

TAG (Task-Action-Guidelines) 구조를 사용한다.
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# 시스템 프롬프트
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """당신은 대한민국 주택임대차 전문 법률 AI 어시스턴트입니다.

역할:
- 임대차 계약서의 조항을 분석하고, 임차인이 이해하기 쉬운 언어로 설명합니다.
- 관련 법령(주택임대차보호법, 민법 등)의 근거를 정확히 제시합니다.
- 법률 전문 용어는 반드시 쉬운 설명을 병기합니다.

임차인 유리/불리 판단 기준:
- 임차인에게 의무·부담·제한을 부과하는 조항 → 불리
- 임차인의 권리를 보호하거나 임대인에게 패널티를 부과하는 조항 → 유리
- 예시 (유리): "보증금 반환 거절/지연 시 이자를 가산한다" → 임대인이 이자를 내야 하므로 임차인 보호 조항
- 예시 (유리): "임대인은 매도 시 임차인에게 우선 통보한다" → 임차인 보호
- 예시 (불리): "수선 책임 전부 임차인 부담" → 임차인에게 불리
- 예시 (불리): "임대인 동의 없이 전대 불가" → 임차인 행동 제한

엄격히 지켜야 할 규칙:
1. 확인되지 않은 법조문 번호를 절대 창작하지 않습니다.
   - 알고 있는 조문만 인용하고, 불확실하면 "관련 법령 확인 필요"로 표기합니다.
2. 항상 한국어로 응답합니다.
3. 조항의 주어(의무를 지는 주체)를 정확히 파악한 후 유불리를 판단합니다.
4. 법률 전문가가 아닌 일반인도 이해할 수 있는 언어를 사용합니다.
"""

# ---------------------------------------------------------------------------
# 위험 조항 분석 프롬프트 (RAG 컨텍스트 포함)
# ---------------------------------------------------------------------------

RISK_ANALYSIS_PROMPT_TEMPLATE = """## Task
임대차 계약서의 위험 조항을 분석하여 임차인에게 알기 쉬운 설명과 법령 근거를 제공하세요.

## 계약 조항
위험도: {risk_level_korean} ({risk_level})
조항 내용:
```
{clause_text}
```

## 관련 법령 (검색 결과)
{law_context}

## Action
다음 JSON 형식으로 정확하게 응답하세요. JSON 외 다른 텍스트는 포함하지 마세요.

```json
{{
  "law_ref": "법령명 제N조 제N항",
  "law_summary": "해당 법령이 규정하는 내용 한 줄 요약",
  "is_favorable": true,
  "explanation": "임차인에게 유리/불리 여부를 먼저 판단한 후 구체적 영향을 쉬운 말로 설명 (2~4문장)",
  "tenant_action": "임차인이 취할 수 있는 구체적 행동 (1~2문장)",
  "severity_reason": "이 조항이 {risk_level_korean}으로 분류된 구체적 이유"
}}
```

## Guidelines
- is_favorable: 조항이 임차인의 권리를 보호하거나 이익이 되면 true, 임차인에게 부담이나 불이익이면 false
- explanation: '임차인에게 유리한 조항입니다.' 또는 '임차인에게 불리한 조항입니다.'로 시작하여 이유 설명
- law_ref: 실제 확인된 법조문만 인용. 불확실하면 "주택임대차보호법 관련 조항"으로 표기
- explanation: 법률 용어 사용 시 괄호 안에 쉬운 설명 병기
- tenant_action: 구체적이고 실행 가능한 행동 제시
- 전체 응답은 반드시 유효한 JSON이어야 함
"""

# ---------------------------------------------------------------------------
# RAG 컨텍스트 없을 때 (ChromaDB 비어있을 때) 폴백 프롬프트
# ---------------------------------------------------------------------------

RISK_ANALYSIS_NO_CONTEXT_PROMPT_TEMPLATE = """## Task
임대차 계약서의 위험 조항을 분석하여 임차인에게 알기 쉬운 설명과 법령 근거를 제공하세요.

## 계약 조항
위험도: {risk_level_korean} ({risk_level})
조항 내용:
```
{clause_text}
```

## Action
참조 법령 데이터베이스를 사용할 수 없는 상황입니다.
알고 있는 주택임대차보호법 지식을 바탕으로 다음 JSON 형식으로 응답하세요.
불확실한 조문 번호는 창작하지 말고 법령명만 기재하세요.

```json
{{
  "law_ref": "주택임대차보호법 (관련 조항 확인 권장)",
  "law_summary": "해당 법령이 규정하는 내용 한 줄 요약 또는 '법령 데이터베이스 확인 필요'",
  "is_favorable": true,
  "explanation": "임차인에게 유리/불리 여부를 먼저 판단한 후 구체적 영향을 쉬운 말로 설명 (2~4문장)",
  "tenant_action": "임차인이 취할 수 있는 구체적 행동 (1~2문장)",
  "severity_reason": "이 조항이 {risk_level_korean}으로 분류된 구체적 이유"
}}
```

## Guidelines
- is_favorable: 조항이 임차인의 권리를 보호하거나 이익이 되면 true, 임차인에게 부담이나 불이익이면 false
- explanation: '임차인에게 유리한 조항입니다.' 또는 '임차인에게 불리한 조항입니다.'로 시작하여 이유 설명
- 확인되지 않은 구체적 조문 번호(제N조)를 절대 만들어내지 않습니다
- explanation: 법률 용어 사용 시 괄호 안에 쉬운 설명 병기
- tenant_action: 구체적이고 실행 가능한 행동 제시
"""

# ---------------------------------------------------------------------------
# 위험도 한국어 레이블 매핑
# ---------------------------------------------------------------------------

RISK_LEVEL_KOREAN = {
    "high": "고위험",
    "medium": "중위험",
    "caution": "주의",
    "safe": "정상",
}

# ---------------------------------------------------------------------------
# 법령 검색 쿼리 생성 프롬프트
# ---------------------------------------------------------------------------

LAW_SEARCH_QUERY_TEMPLATE = """임대차 계약 조항: "{clause_text}"
위험도: {risk_level_korean}

이 조항과 관련된 주택임대차보호법 또는 민법 조항을 찾기 위한
핵심 검색 키워드 3개를 쉼표로 구분하여 나열하세요.
예시: 보증금 반환, 임차인 보호, 대항력
키워드만 나열하고 다른 텍스트는 포함하지 마세요."""


def build_risk_analysis_prompt(
    clause_text: str,
    risk_level: str,
    law_context: str = "",
) -> str:
    """
    위험 조항 분석을 위한 사용자 프롬프트를 생성한다.

    Parameters
    ----------
    clause_text : str
        분석할 조항 원문
    risk_level : str
        "high" | "medium" | "caution"
    law_context : str
        ChromaDB 검색 결과 법령 텍스트. 비어있으면 폴백 프롬프트 사용.

    Returns
    -------
    str
        GPT-4o user 메시지 내용
    """
    risk_korean = RISK_LEVEL_KOREAN.get(risk_level, risk_level)

    if law_context.strip():
        template = RISK_ANALYSIS_PROMPT_TEMPLATE
    else:
        template = RISK_ANALYSIS_NO_CONTEXT_PROMPT_TEMPLATE

    return template.format(
        clause_text=clause_text,
        risk_level=risk_level,
        risk_level_korean=risk_korean,
        law_context=law_context,
    )


def build_search_query_prompt(clause_text: str, risk_level: str) -> str:
    """ChromaDB 검색에 사용할 쿼리 생성 프롬프트를 반환한다."""
    risk_korean = RISK_LEVEL_KOREAN.get(risk_level, risk_level)
    return LAW_SEARCH_QUERY_TEMPLATE.format(
        clause_text=clause_text[:200],
        risk_level_korean=risk_korean,
    )


# ---------------------------------------------------------------------------
# 독립 테스트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== 프롬프트 모듈 독립 테스트 ===\n")

    # 법령 컨텍스트 있는 경우
    prompt_with_context = build_risk_analysis_prompt(
        clause_text="임대인 동의 없이 전대하거나 임차권을 양도할 수 없다.",
        risk_level="high",
        law_context="주택임대차보호법 제3조: 임대차는 그 등기가 없는 경우에도 임차인이 주택의 인도와 주민등록을 마친 때에는 그 다음 날부터 제3자에 대하여 효력이 생긴다.",
    )
    print("[프롬프트 - 컨텍스트 있음]")
    print(prompt_with_context[:300])
    print("...\n")

    # 법령 컨텍스트 없는 경우 (폴백)
    prompt_no_context = build_risk_analysis_prompt(
        clause_text="보증금 반환 거절 시 연 12% 이자를 부과한다.",
        risk_level="high",
        law_context="",
    )
    print("[프롬프트 - 컨텍스트 없음 (폴백)]")
    print(prompt_no_context[:300])
    print("...\n")

    # 검색 쿼리 프롬프트
    search_prompt = build_search_query_prompt(
        clause_text="수선 책임은 임차인이 부담한다.",
        risk_level="medium",
    )
    print("[검색 쿼리 프롬프트]")
    print(search_prompt)
    print("\n프롬프트 모듈 테스트 완료.")
