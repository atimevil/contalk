"""
위험도 분류기 — KLUE-RoBERTa 기반 (학습 전 단계: rule-based 폴백 포함)

위험도 레이블:
    high    — 고위험: 임차인 권리를 심각하게 침해하는 조항
    medium  — 중위험: 분쟁 가능성이 있거나 주의가 필요한 조항
    caution — 주의:   생활 제약이나 경미한 불이익 조항
    safe    — 정상:   문제 없는 표준 조항
"""
from __future__ import annotations

import logging
import os
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Rule-based 폴백 키워드 매핑
# ---------------------------------------------------------------------------

# 각 항목: (패턴, 위험도)  — 위에서 아래로 우선순위 높음
_RISK_RULES: List[Tuple[re.Pattern, str]] = [
    # ── 고위험 ──────────────────────────────────────────────────────────────
    # 임대인 동의 없이 → 위험 (전대금지 아님, "없이"가 핵심)
    (re.compile(r"임대인\s*(?:의\s*)?동의\s*없이"), "high"),
    # 보증금 반환 거절/지연 관련
    (re.compile(r"보증금\s*반환\s*(?:거절|거부|지연)"), "high"),
    # 계약 해지 불가
    (re.compile(r"계약\s*해지\s*(?:불가|할\s*수\s*없|금지)"), "high"),
    # 임차인 귀책 없이 계약 해제
    (re.compile(r"임대인(?:이)?\s*(?:언제든지|일방적으로)\s*(?:해지|해제)"), "high"),
    # 보증금 공제 (사유 없이)
    (re.compile(r"보증금에서\s*(?:일방적으로|무조건)\s*공제"), "high"),
    # 대항력 포기
    (re.compile(r"대항력\s*포기"), "high"),
    # 확정일자 신청 금지
    (re.compile(r"확정일자\s*(?:신청\s*)?금지"), "high"),
    # 임차권 등기 금지
    (re.compile(r"임차권\s*등기\s*(?:신청\s*)?금지"), "high"),
    # ── 중위험 ──────────────────────────────────────────────────────────────
    # 수선 책임 전가
    (re.compile(r"수선\s*(?:책임|의무|비용)"), "medium"),
    # 원상복구 광범위 적용
    (re.compile(r"원상복구"), "medium"),
    # 관리비 부담 (임차인)
    (re.compile(r"관리비\s*(?:전액\s*)?부담"), "medium"),
    # 보증금 이자 없음
    (re.compile(r"보증금\s*이자\s*(?:없|불지급|미지급)"), "medium"),
    # 중도해지 위약금
    (re.compile(r"중도\s*해지\s*(?:위약금|손해배상)"), "medium"),
    # 임의 방문/출입
    (re.compile(r"임대인\s*(?:이)?\s*(?:언제든지|사전\s*통보\s*없이)\s*(?:방문|출입)"), "medium"),
    # 연체 고율 이자
    (re.compile(r"연체\s*(?:이자|이율)\s*(?:연|월)\s*\d+\s*%"), "medium"),
    # ── 주의 ────────────────────────────────────────────────────────────────
    # 전대 금지
    (re.compile(r"전대\s*(?:금지|불가|할\s*수\s*없)"), "caution"),
    # 반려동물 금지
    (re.compile(r"반려\s*동물|애완\s*동물"), "caution"),
    # 흡연 금지
    (re.compile(r"흡연\s*(?:금지|불가)"), "caution"),
    # 인테리어/시설 변경 금지
    (re.compile(r"(?:인테리어|시설|구조)\s*(?:변경|개조|공사)\s*금지"), "caution"),
    # 세탁기/에어컨 등 설치 금지
    (re.compile(r"(?:세탁기|에어컨|에어컨디셔너)\s*설치\s*금지"), "caution"),
    # 전입신고 제한
    (re.compile(r"전입신고\s*(?:금지|제한|불가)"), "caution"),
]


# ---------------------------------------------------------------------------
# 공개 인터페이스
# ---------------------------------------------------------------------------

def classify_risk(clauses: List[dict]) -> List[dict]:
    """
    조항 목록의 각 조항에 위험도를 부여한다.

    KLUE-RoBERTa 모델이 로드되면 모델 기반 분류를 사용하고,
    없으면 rule-based 폴백을 사용한다.

    Parameters
    ----------
    clauses : List[dict]
        parse_clauses() 반환값
        각 항목: {"number": str, "title": str, "text": str, "items": list}

    Returns
    -------
    List[dict]
        입력 clauses에 "risk" 필드가 추가된 목록
        각 항목: {"number": str, ..., "risk": "high"|"medium"|"caution"|"safe"}
    """
    model = _load_model_once()

    result = []
    for clause in clauses:
        if model is not None:
            risk = _classify_with_model(model, clause["text"])
        else:
            risk = _classify_with_rules(clause["text"])

        result.append({**clause, "risk": risk})

    return result


# ---------------------------------------------------------------------------
# 모델 로딩 (싱글톤)
# ---------------------------------------------------------------------------

_MODEL_CACHE: Optional[object] = None
_MODEL_LOAD_ATTEMPTED = False


def _load_model_once():
    """KLUE-RoBERTa 모델을 한 번만 로드한다. 실패 시 None 반환."""
    global _MODEL_CACHE, _MODEL_LOAD_ATTEMPTED

    if _MODEL_LOAD_ATTEMPTED:
        return _MODEL_CACHE

    _MODEL_LOAD_ATTEMPTED = True
    model_path = os.environ.get("KLUE_ROBERTA_MODEL_PATH", "")

    if not model_path:
        logger.info(
            "KLUE_ROBERTA_MODEL_PATH 미설정 — rule-based 폴백 사용. "
            "모델 파인튜닝 후 경로를 환경변수로 설정하세요."
        )
        return None

    try:
        from transformers import pipeline as hf_pipeline  # type: ignore

        classifier = hf_pipeline(
            "text-classification",
            model=model_path,
            tokenizer=model_path,
            device=-1,  # CPU; GPU 사용 시 device=0
            truncation=True,
            max_length=512,
        )
        logger.info("KLUE-RoBERTa 모델 로드 성공: %s", model_path)
        _MODEL_CACHE = classifier
        return classifier

    except ImportError:
        logger.warning("transformers 패키지 미설치 — rule-based 폴백 사용")
        return None
    except Exception as exc:
        logger.warning("모델 로드 실패: %s — rule-based 폴백 사용", exc)
        return None


# ---------------------------------------------------------------------------
# 모델 기반 분류
# ---------------------------------------------------------------------------

# 모델 출력 레이블 → 표준 레이블 매핑 (파인튜닝 시 설정한 레이블에 맞게 수정)
_MODEL_LABEL_MAP = {
    "LABEL_0": "safe",
    "LABEL_1": "caution",
    "LABEL_2": "medium",
    "LABEL_3": "high",
    # 파인튜닝에서 직접 레이블명 설정한 경우
    "normal": "safe",
    "safe": "safe",
    "caution": "caution",
    "medium": "medium",
    "high": "high",
}


def _classify_with_model(model, text: str) -> str:
    """파인튜닝된 KLUE-RoBERTa로 위험도를 분류한다."""
    try:
        # 텍스트가 너무 길면 앞 400자 사용 (토크나이저 최대 512 토큰)
        truncated = text[:400] if len(text) > 400 else text
        predictions = model(truncated)

        if not predictions:
            return "safe"

        label_raw = predictions[0]["label"]
        label = _MODEL_LABEL_MAP.get(label_raw, "safe")
        return label

    except Exception as exc:
        logger.warning("모델 추론 실패: %s — rule-based 폴백", exc)
        return _classify_with_rules(text)


# ---------------------------------------------------------------------------
# Rule-based 분류 폴백
# ---------------------------------------------------------------------------

def _classify_with_rules(text: str) -> str:
    """키워드 패턴으로 위험도를 분류한다."""
    if not text:
        return "safe"

    # 전처리: 공백 정규화
    normalized = re.sub(r"\s+", " ", text).strip()

    # 우선순위 순서로 패턴 검사
    for pattern, risk in _RISK_RULES:
        if pattern.search(normalized):
            return risk

    return "safe"


# ---------------------------------------------------------------------------
# 독립 테스트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    test_clauses = [
        {
            "number": "제1조",
            "title": "목적",
            "text": "본 계약은 아래 부동산에 대한 임대차 계약을 체결함을 목적으로 한다.",
            "items": [],
        },
        {
            "number": "제2조",
            "title": "임대차 기간",
            "text": "임대차 기간은 2024년 3월 1일부터 2026년 2월 28일까지로 한다.",
            "items": [],
        },
        {
            "number": "제5조",
            "title": "임차인의 의무",
            "text": (
                "임차인은 임대인 동의 없이 목적물을 전대하거나 임차권을 양도할 수 없다. "
                "계약 종료 시 원상복구 의무를 진다. 반려동물 사육으로 인한 손상은 임차인 부담이다."
            ),
            "items": ["① 선량한 관리자의 주의", "② 전대 금지", "③ 원상복구"],
        },
        {
            "number": "특약사항",
            "title": "",
            "text": (
                "보증금 반환 거절 시 연 12%의 이자를 가산한다. "
                "흡연은 금지한다. "
                "임대인은 언제든지 해지할 수 있다."
            ),
            "items": [],
        },
        {
            "number": "제3조",
            "title": "수선 책임",
            "text": "수선 책임은 임대인이 부담하되, 소모성 부품의 교체 및 원상복구는 임차인이 부담한다.",
            "items": [],
        },
    ]

    print("=== 분류기 독립 테스트 ===\n")
    print(f"KLUE_ROBERTA_MODEL_PATH: {os.environ.get('KLUE_ROBERTA_MODEL_PATH', '(미설정 — rule-based 폴백)')}\n")

    results = classify_risk(test_clauses)

    print("분류 결과:")
    for r in results:
        risk_emoji = {"high": "🔴", "medium": "🟠", "caution": "🟡", "safe": "✅"}.get(r["risk"], "?")
        print(f"  [{r['number']}] {risk_emoji} {r['risk']:8s} | {r['text'][:60]}...")

    print()

    # Rule-based 직접 테스트
    print("Rule-based 직접 테스트:")
    tests = [
        ("임대인 동의 없이 전대할 수 없다", "high"),
        ("보증금 반환 거절 시 이자 부과", "high"),
        ("수선 책임은 임차인이 부담한다", "medium"),
        ("원상복구 의무가 있다", "medium"),
        ("반려동물 사육 금지", "caution"),
        ("흡연 금지", "caution"),
        ("임대차 기간은 2년으로 한다", "safe"),
    ]

    for text, expected in tests:
        result = _classify_with_rules(text)
        status = "PASS" if result == expected else f"FAIL (예상: {expected})"
        print(f"  [{status}] {result:8s} | {text}")
