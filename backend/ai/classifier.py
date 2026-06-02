"""
위험도 분류기 — KLUE-RoBERTa(3-class) + 치명 위험 규칙 승격 하이브리드.

위험도 레이블:
    high    — 고위험: 전세사기·깡통전세 등 치명적 위험.
              모델이 아닌 규칙(_CRITICAL_PATTERNS)으로만 부여한다.
    medium  — 중위험: 분쟁 가능성이 있거나 주의가 필요한 조항
    caution — 주의:   생활 제약이나 경미한 불이익 조항
    safe    — 정상:   문제 없는 표준 조항

설계 결정 (이전 "high 4번째 클래스 추가" TODO 해결):
    모델은 3-class(medium/caution/safe)만 학습·예측한다 — high는 라벨 경계가 모호하고
    학습 데이터가 적어 별도 클래스로 두지 않는다. 대신 전세사기/깡통전세 같은
    치명 위험은 _CRITICAL_PATTERNS 규칙으로 high로 승격하여 미탐(false negative)을 막는다.
    이 규칙 승격은 모델/일반 규칙보다 항상 우선한다.
"""
from __future__ import annotations

import logging
import os
import re
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 치명 위험 규칙 — high 승격 (모델/일반 규칙보다 최우선)
# 전세사기·깡통전세 등 임차인에게 치명적인 조항. 정밀 패턴으로 과탐을 억제한다.
# ---------------------------------------------------------------------------

_CRITICAL_PATTERNS: List[re.Pattern] = [
    # 신탁 부동산을 수탁자(신탁회사) 동의 없이 임대 — 전세사기 전형
    re.compile(r"신탁.{0,40}(?:동의|승낙)\s*없이"),
    re.compile(r"신탁회사\s*동의\s*없이"),
    # 근저당이 임차인 대항력보다 선순위 / 전입신고 당일 추가 근저당 — 대항력 무력화
    re.compile(r"대항력보다\s*선순위"),
    re.compile(r"전입신고일?\s*당일.{0,15}근저당"),
    re.compile(r"(?:추가\s*)?근저당(?:권)?\s*(?:을|를)?\s*설정할\s*수\s*있"),
    # 선순위 담보(근저당) 내역 고지 거부
    re.compile(r"근저당(?:권)?.{0,20}(?:별도\s*)?고지\s*(?:하지\s*않|거부)"),
    # 우선변제권 배제 / 주장 불가
    re.compile(r"우선\s*(?:변제|정산).{0,20}(?:주장할\s*수\s*없|배제|포기)"),
    # 보증금 반환 보증보험 가입 권리 포기
    re.compile(r"보증\s*보험\s*가입.{0,15}포기"),
    # 깡통전세: 매매가-전세가 차액 없음 / 전세가율 90%+
    re.compile(r"매매가.{0,15}전세가.{0,20}차액이?\s*없"),
    re.compile(r"시세\s*대비\s*9\d\s*%"),
    # 전입신고 절대 금지 (대항력 취득 원천 차단)
    re.compile(r"전입신고를?\s*(?:절대\s*)?하지\s*않"),
    # 계약갱신요구권 사전 포기
    re.compile(r"갱신\s*요구권.{0,15}(?:일체\s*)?(?:포기|행사하지\s*않)"),
]


def _is_critical(text: str) -> bool:
    """치명 위험 패턴(전세사기/깡통전세 등) 매치 여부."""
    if not text:
        return False
    normalized = re.sub(r"\s+", " ", text).strip()
    return any(p.search(normalized) for p in _CRITICAL_PATTERNS)


# ---------------------------------------------------------------------------
# Rule-based 폴백 키워드 매핑
# ---------------------------------------------------------------------------

# 각 항목: (패턴, 위험도)  — 위에서 아래로 우선순위 높음
_RISK_RULES: List[Tuple[re.Pattern, str]] = [
    # ── 중위험 (구 고위험 포함 — 3-class 통일) ───────────────────────────────
    # 임대인 동의 없이 → 위험 (전대금지 아님, "없이"가 핵심)
    (re.compile(r"임대인\s*(?:의\s*)?동의\s*없이"), "medium"),
    # 보증금 반환 거절 시 이자 가산 → caution (임대인 패널티, 임차인 보호 조항)
    (re.compile(r"보증금\s*반환\s*(?:을|이)?\s*(?:거절|지연)\s*시.{0,50}(?:이자|이율).{0,15}가산"), "caution"),
    (re.compile(r"보증금\s*반환\s*(?:을|이)?\s*(?:거절|지연)\s*시.{0,30}연\s*\d+\s*%"), "caution"),
    # 보증금 반환 거절/지연 단독 → medium (임차인 불리)
    # 조사(을/이/에 대해 등) 허용
    (re.compile(r"보증금\s*반환\s*(?:을|이|에\s*대해)?\s*(?:거절|거부|지연)"), "medium"),
    # 계약 해지 불가
    (re.compile(r"계약\s*(?:을|을\s*)?해지\s*(?:불가|할\s*수\s*없|금지)"), "medium"),
    # 임대인이 언제든지/일방적으로 해지 — 중간에 목적어 허용 (예: "계약을 해지")
    (re.compile(r"임대인\s*(?:이|은)?\s*(?:언제든지|일방적으로).{0,15}(?:해지|해제)"), "medium"),
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
    # 임의 방문/출입 — 중간에 목적어 허용
    (re.compile(r"임대인\s*(?:이|은)?\s*(?:언제든지|사전\s*통보\s*없이).{0,15}(?:방문|출입)"), "medium"),
    # 연체 고율 이자 — "이자율", "이자", "이율" 모두 허용
    (re.compile(r"연체\s*(?:이자율?|이율)\s*(?:연|월)\s*\d+\s*%"), "medium"),
    # 임차인 부담 명시 (광범위 비용 전가)
    (re.compile(r"(?:비용|손해|손실)\s*(?:은|는)?\s*임차인\s*(?:이|가)?\s*부담"), "medium"),
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
        text = clause["text"]
        # 0. 치명 위험 규칙 — 모델/일반 규칙보다 최우선 high 승격
        if _is_critical(text):
            logger.debug("치명 위험 high 승격 | %.50s...", text)
            risk = "high"
        elif model is not None:
            risk = _classify_with_model(model, text)
        else:
            risk = _classify_with_rules(text)

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
        from transformers import (  # type: ignore
            AutoModelForSequenceClassification,
            AutoTokenizer,
            pipeline as hf_pipeline,
        )

        # num_labels=3 명시 — config.json의 null 값 우회
        # id2label: {0: safe, 1: caution, 2: medium}
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_path,
            num_labels=3,
            ignore_mismatched_sizes=False,
        )
        classifier = hf_pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
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

    현재 모델 특성:
      - medium 클래스 예측 확률이 매우 낮음 (훈련 데이터 불균형 이슈)
      - safe / caution 구분은 모델이 잘 수행
      - medium 탐지는 규칙 기반이 더 신뢰도 높음

    우선순위:
      1. 규칙이 medium → 무조건 medium 채택 (모델 False Negative 보완)
      2. Safe 오버라이드: 규칙=safe + known-safe 패턴 → safe 강제
      3. 다운그레이드: 모델=medium + 임차인 보호 패턴 → caution으로 낮춤
      4. 규칙 업그레이드: 규칙 > 모델 → 규칙 채택
      5. 기본: 모델 결과 사용 (safe/caution 구분은 모델이 우세)
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

        # ── 1. 규칙이 medium → safe 오버라이드 패턴 없으면 즉시 medium 반환 ─────
        # 현재 모델의 medium 예측 확률이 ~0.003으로 사실상 0이므로
        # medium 탐지는 규칙 기반에 완전히 위임한다.
        # 단, safe 오버라이드 패턴(명백한 안전 조항)이 있으면 safe를 유지한다.
        if rule_label == "medium":
            for pattern in _SAFE_OVERRIDE_PATTERNS:
                if pattern.search(normalized):
                    logger.debug("Safe 오버라이드(medium 억제) | %.50s...", text)
                    return "safe"
            logger.debug("규칙 medium 우선 채택 | %.50s...", text)
            return "medium"

        # ── 2. Safe 오버라이드 ───────────────────────────────────────────────
        # 규칙이 safe이고 명백히 안전한 조항 패턴이 있으면 → safe 강제
        if rule_label == "safe":
            for pattern in _SAFE_OVERRIDE_PATTERNS:
                if pattern.search(normalized):
                    logger.debug("Safe 오버라이드 | %.50s...", text)
                    return "safe"

        # ── 3. 다운그레이드 ─────────────────────────────────────────────────
        # 모델이 medium인데 임차인 보호 패턴이 있으면 caution으로 낮춤
        if model_label == "medium":
            for pattern in _DOWNGRADE_TO_CAUTION:
                if pattern.search(normalized):
                    logger.debug("다운그레이드 medium → caution | %.50s...", text)
                    model_label = "caution"
                    break

        # ── 4. 규칙 업그레이드 ──────────────────────────────────────────────
        # (medium 제외) 규칙이 더 높은 위험도를 감지하면 채택
        if _RISK_ORDER.get(rule_label, 0) > _RISK_ORDER.get(model_label, 0):
            logger.debug(
                "규칙 업그레이드: %s → %s | %.30s...",
                model_label, rule_label, text,
            )
            return rule_label

        # ── 5. 모델 결과 사용 (safe/caution 구분) ───────────────────────────
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
