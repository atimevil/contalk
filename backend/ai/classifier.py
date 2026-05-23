"""
위험도 분류기 — KLUE-RoBERTa 기반 (학습 전 단계: rule-based 폴백 포함)

위험도 레이블 (3-class):
    medium  — 중위험: 분쟁 가능성이 있거나 주의가 필요한 조항
    caution — 주의:   생활 제약이나 경미한 불이익 조항
    safe    — 정상:   문제 없는 표준 조항

# TODO: "high" 4번째 클래스 추가 여부는 별도 레이블링 작업 완료 후 결정
#       추가 시 train.py _LABEL2ID, _RISK_RULES, _MODEL_LABEL_MAP, pipeline.py 동시 수정 필요
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
    # ── 중위험 (구 고위험 포함 — 3-class 통일) ───────────────────────────────
    # 임대인 동의 없이 → 위험 (전대금지 아님, "없이"가 핵심)
    (re.compile(r"임대인\s*(?:의\s*)?동의\s*없이"), "medium"),
    # 보증금 반환 거절 시 이자 가산 → caution (임대인 패널티, 임차인 보호 조항)
    (re.compile(r"보증금\s*반환\s*(?:거절|지연)\s*시.{0,50}(?:이자|이율).{0,15}가산"), "caution"),
    (re.compile(r"보증금\s*반환\s*(?:거절|지연)\s*시.{0,30}연\s*\d+\s*%"), "caution"),
    # 보증금 반환 거절/지연 단독 → medium (임차인 불리)
    (re.compile(r"보증금\s*반환\s*(?:거절|거부|지연)"), "medium"),
    # 계약 해지 불가
    (re.compile(r"계약\s*해지\s*(?:불가|할\s*수\s*없|금지)"), "medium"),
    # 임차인 귀책 없이 계약 해제
    (re.compile(r"임대인\s*(?:이|은)?\s*(?:언제든지|일방적으로)\s*(?:해지|해제)"), "medium"),
    # 보증금 공제 (사유 없이)
    (re.compile(r"보증금에서\s*(?:일방적으로|무조건)\s*공제"), "medium"),
    # 대항력 포기
    (re.compile(r"대항력\s*포기"), "medium"),
    # 확정일자 신청 금지
    (re.compile(r"확정일자\s*(?:신청\s*)?금지"), "medium"),
    # 임차권 등기 금지
    (re.compile(r"임차권\s*등기\s*(?:신청\s*)?금지"), "medium"),
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
    (re.compile(r"임대인\s*(?:이|은)?\s*(?:언제든지|사전\s*통보\s*없이)\s*(?:방문|출입)"), "medium"),
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
# Safe 오버라이드 — 모델이 FP를 내는 명백히 안전한 조항 패턴
# (규칙도 safe이고 아래 패턴이 매치되면 모델 결과 무시 → safe 강제)
# ---------------------------------------------------------------------------

_SAFE_OVERRIDE_PATTERNS: List[re.Pattern] = [
    # 계약 목적 조항 ("임대차 계약을 체결함을 목적으로 한다")
    re.compile(r"임대차\s*계약을\s*(?:체결함을\s*)?목적\s*으로\s*한다"),
    # 기간 명시 조항 (YYYY년 ~ YYYY년 형태의 임대 기간)
    re.compile(r"임대차\s*기간은\s*\d{4}년.{1,40}\d{4}년"),
    # 퇴거 후 N일 이내 보증금 반환 (임차인 보호)
    re.compile(r"보증금\s*반환(?:은|을)?\s*임차인\s*퇴거\s*후\s*\d+일"),
    # 임대인 매도 시 임차인 우선 통보 (임차인 보호)
    re.compile(r"임대인.{0,15}매도.{0,30}임차인.{0,15}(?:우선\s*)?통보"),
]

# ---------------------------------------------------------------------------
# 다운그레이드 — 임차인 보호 패턴이 있으면 model "medium" → "caution"으로 낮춤
# ---------------------------------------------------------------------------

_DOWNGRADE_TO_CAUTION: List[re.Pattern] = [
    # 보증금 반환 거절/지연 시 이자 가산 (임대인 패널티 → 임차인 보호 특약)
    re.compile(r"보증금\s*반환\s*(?:거절|지연)\s*시.{0,50}(?:이자|이율).{0,15}가산"),
    re.compile(r"보증금\s*반환\s*(?:거절|지연)\s*시.{0,30}연\s*\d+\s*%"),
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

# 모델 출력 레이블 → 표준 레이블 매핑 (train.py _LABEL2ID와 동기화)
# 현재 3-class: safe=0, caution=1, medium=2
_MODEL_LABEL_MAP = {
    "LABEL_0": "safe",
    "LABEL_1": "caution",
    "LABEL_2": "medium",
    # 파인튜닝에서 직접 레이블명 설정한 경우
    "normal": "safe",
    "safe": "safe",
    "caution": "caution",
    "medium": "medium",
}


# 위험도 우선순위 (하이브리드 비교용)
_RISK_ORDER = {"medium": 2, "caution": 1, "safe": 0}


def _classify_with_model(model, text: str) -> str:
    """
    파인튜닝된 KLUE-RoBERTa + 규칙 기반 하이브리드 분류.

    우선순위:
      1. Safe 오버라이드: 규칙=safe + known-safe 패턴 → 모델 무시, safe 반환
      2. 다운그레이드: 모델=medium + 임차인 보호 패턴 → caution으로 낮춤
      3. 규칙 업그레이드: 규칙 > 모델 → 규칙 채택 (False Negative 방지)
      4. 기본: 모델 결과 사용
    """
    try:
        truncated = text[:400] if len(text) > 400 else text
        predictions = model(truncated)

        if not predictions:
            return _classify_with_rules(text)

        label_raw = predictions[0]["label"]
        model_label = _MODEL_LABEL_MAP.get(label_raw, "safe")
        rule_label = _classify_with_rules(text)
        normalized = re.sub(r"\s+", " ", text).strip()

        # ── 1. Safe 오버라이드 ───────────────────────────────────────────────
        # 규칙이 safe이고 명백히 안전한 조항 패턴이 있으면 → safe 강제
        if rule_label == "safe":
            for pattern in _SAFE_OVERRIDE_PATTERNS:
                if pattern.search(normalized):
                    logger.debug("Safe 오버라이드 | %.50s...", text)
                    return "safe"

        # ── 2. 다운그레이드 ─────────────────────────────────────────────────
        # 모델이 medium인데 임차인 보호 패턴이 있으면 caution으로 낮춤
        if model_label == "medium":
            for pattern in _DOWNGRADE_TO_CAUTION:
                if pattern.search(normalized):
                    logger.debug("다운그레이드 medium → caution | %.50s...", text)
                    model_label = "caution"
                    break

        # ── 3. 규칙 업그레이드 ──────────────────────────────────────────────
        # 규칙이 더 높은 위험도를 감지하면 채택 (모델 False Negative 방지)
        if _RISK_ORDER.get(rule_label, 0) > _RISK_ORDER.get(model_label, 0):
            logger.debug(
                "규칙 업그레이드: %s → %s | %.30s...",
                model_label, rule_label, text,
            )
            return rule_label

        return model_label

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
        risk_emoji = {"medium": "🟠", "caution": "🟡", "safe": "✅"}.get(r["risk"], "?")
        print(f"  [{r['number']}] {risk_emoji} {r['risk']:8s} | {r['text'][:60]}...")

    print()

    # Rule-based 직접 테스트
    print("Rule-based 직접 테스트:")
    tests = [
        ("임대인 동의 없이 전대할 수 없다", "medium"),
        ("보증금 반환 거절 시 이자 부과", "medium"),
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
