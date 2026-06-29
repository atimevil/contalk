"""
조항 파서 — 임대차 계약서 원문 텍스트에서 조항을 구조화된 리스트로 변환한다.

지원 패턴:
    - 한국 표준: 제1조, 제2조 (목적), 제3조의2
    - 숫자+점:   1. 임대 기간, 2. 보증금
    - 특약사항:  전체를 단일 조항으로 처리
    - 항(項):    ① ② ③ (단독 파싱 또는 상위 조항에 포함)
"""
from __future__ import annotations

import re
from typing import List


# ---------------------------------------------------------------------------
# 공개 인터페이스
# ---------------------------------------------------------------------------

def parse_clauses(raw_text: str) -> List[dict]:
    """
    OCR로 추출된 원문 텍스트를 조항 단위로 파싱한다.

    Parameters
    ----------
    raw_text : str
        OCR 결과 전체 텍스트

    Returns
    -------
    List[dict]
        [
            {
                "number": "제1조",          # 조항 번호 (없으면 "특약사항" 등)
                "title":  "목적",           # 조항 제목 (있으면)
                "text":   "본 계약은 ...",  # 조항 본문 전체
                "items":  ["① ...", "② ..."]  # 항 목록 (파싱된 경우)
            },
            ...
        ]
    """
    if not raw_text or not raw_text.strip():
        return []

    # 전처리: 공백 정규화
    text = _normalize_whitespace(raw_text)

    clauses = _split_by_article(text)

    if not clauses:
        # 한국식 조항 번호가 없는 경우 숫자 점 패턴 시도
        clauses = _split_by_numeric(text)

    if not clauses:
        # 그래도 없으면 전체를 단일 조항으로 반환
        clauses = [{"number": "전문", "title": "", "text": text.strip(), "items": []}]

    # 각 조항 내 항(項) 파싱
    for clause in clauses:
        clause["items"] = _extract_items(clause["text"])

    return clauses


# ---------------------------------------------------------------------------
# 내부 파싱 함수
# ---------------------------------------------------------------------------

# 조항 번호 패턴: 제N조, 제N조의M, 제N조 (제목)
_ARTICLE_PATTERN = re.compile(
    r"""
    (?:^|\n)                        # 줄 시작 또는 줄바꿈 뒤
    (제\s*\d+\s*조(?:\s*의\s*\d+)?  # 제N조 또는 제N조의M
    (?:\s*[\(\（]([^\)\）]{0,40})[\)\）])? # 선택적 제목 (괄호)
    )
    \s*                             # 공백
    """,
    re.VERBOSE | re.MULTILINE,
)

# 특약사항 패턴
# 줄 시작 뒤 글머리 기호/괄호(■ ● ▶ ◆ ※ 【 [ ( 등) 접두를 허용한다.
# PDF 헤더가 "■ 특약사항", "【특약사항】" 형태인 경우 매치 실패로 특약이
# 통째로 누락되던 버그(special_clauses 0) 대응.
_SPECIAL_BULLET = r"[\s■●▶◆◇※○◎•·∙★☆▣□【\[\(]*"
_SPECIAL_PATTERN = re.compile(
    r"(?:^|\n)" + _SPECIAL_BULLET + r"(특약\s*사항|특별\s*약정|특기\s*사항|붙임\s*사항)",
    re.MULTILINE,
)

# 특약 블록 내부의 개별 번호 항목 ("1. ", "2) " 등 — 줄 시작)
_SPECIAL_ITEM_SPLIT = re.compile(r"(?:^|\n)\s*(\d{1,2})[\.\)]\s+")
# 특약 헤더(특약사항/특별약정 등) 제거용 — 글머리 기호 접두도 함께 제거
_SPECIAL_HEADER = re.compile(
    r"^" + _SPECIAL_BULLET + r"(?:특약\s*사항|특별\s*약정|특기\s*사항|붙임\s*사항)\s*"
)


def _split_special(special_text: str) -> List[dict]:
    """특약 블록을 개별 특약 항목(번호별)으로 분리한다.

    표준계약서에서 여러 특약이 "특약사항" 한 덩어리로 묶이면 위험도가 희석되어
    분석에서 누락(false negative)된다. 번호 항목별로 쪼개 각 특약이 독립적으로
    위험도 분류되도록 한다. 번호 항목이 없으면 단일 조항으로 둔다.
    """
    body = _SPECIAL_HEADER.sub("", special_text, count=1)
    parts = _SPECIAL_ITEM_SPLIT.split(body)

    # split 결과: [머리말, 번호1, 본문1, 번호2, 본문2, ...]
    if len(parts) < 3:
        return [{"number": "특약사항", "title": "", "text": special_text.strip(), "items": []}]

    clauses: List[dict] = []
    pre = re.sub(r"\s+", " ", parts[0]).strip()
    if pre:  # ※ 현황 등 머리말 보존
        clauses.append({"number": "특약사항", "title": "", "text": pre, "items": []})

    for num, item_body in zip(parts[1::2], parts[2::2]):
        txt = re.sub(r"\s+", " ", item_body).strip()
        if txt:
            clauses.append({"number": f"특약 {num}", "title": "", "text": txt, "items": []})

    return clauses or [{"number": "특약사항", "title": "", "text": special_text.strip(), "items": []}]

# 숫자점 패턴: 1. 또는 (1)
_NUMERIC_PATTERN = re.compile(
    r"(?:^|\n)(\d{1,2}[\.．]\s+|\(\d{1,2}\)\s+)",
    re.MULTILINE,
)

# 항(項) 패턴: ① ② ③ ... ⑳ 또는 ①②③ circled digits
_ITEM_PATTERN = re.compile(
    r"[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]",
)


def _has_legal_content(text: str) -> bool:
    """
    텍스트에 법적 효력이 있는 실질적인 내용이 있는지 판단한다.

    단순 당사자 정보(임대인 이름, 날짜, 서명란 등)만 있는 전문(前文)은
    분석 대상이 아니므로 False를 반환한다.
    """
    legal_endings = re.compile(
        r"(?:한다|하여야\s*한다|할\s*수\s*없다|아니한다|받는다|진다\.|부담한다|"
        r"금지한다|인정한다|갈음한다|있다|없다|따른다|의한다)"
    )
    return bool(legal_endings.search(text))


def _normalize_whitespace(text: str) -> str:
    """연속된 공백/빈 줄을 정리하고 전각 문자를 반각으로 변환."""
    # 전각 공백 → 반각
    text = text.replace("　", " ")
    # 캐리지리턴 정리
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # 3줄 이상 연속 빈 줄을 2줄로
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def _split_by_article(text: str) -> List[dict]:
    """제N조 패턴으로 텍스트를 분리한다."""
    matches = list(_ARTICLE_PATTERN.finditer(text))

    if not matches:
        return []

    clauses = []
    for i, match in enumerate(matches):
        number_raw = match.group(1).strip()
        # 숫자/공백 정규화: "제 1 조" → "제1조"
        number = re.sub(r"\s+", "", number_raw.split("(")[0].split("（")[0])
        title_match = re.search(r"[\(\（]([^\)\）]+)[\)\）]", number_raw)
        title = title_match.group(1).strip() if title_match else ""

        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        # 특약사항 감지
        special_match = _SPECIAL_PATTERN.search(body)
        if special_match:
            # 특약사항 이전 부분을 현재 조항에
            pre_special = body[: special_match.start()].strip()
            special_text = body[special_match.start():].strip()

            if pre_special:
                clauses.append(
                    {"number": number, "title": title, "text": pre_special, "items": []}
                )
            # 특약사항을 개별 특약 항목으로 분리하여 추가
            clauses.extend(_split_special(special_text))
        else:
            clauses.append(
                {"number": number, "title": title, "text": body, "items": []}
            )

    # 첫 번째 조항 이전 전문(前文)이 있으면 추가
    # 단, 당사자 정보(이름·날짜·서명란)만 있는 경우는 분석 대상이 아니므로 제외
    preamble = text[: matches[0].start()].strip()
    if preamble and _has_legal_content(preamble):
        clauses.insert(
            0, {"number": "전문", "title": "", "text": preamble, "items": []}
        )

    # 특약사항만 별도 존재하는 경우 (조항 번호 없음)
    _inject_standalone_special(text, matches, clauses)

    return clauses


def _inject_standalone_special(
    text: str, matches: list, clauses: List[dict]
) -> None:
    """조항 목록에 없는 독립 특약사항을 마지막 조항 뒤에 추가."""
    if not matches:
        return
    tail = text[matches[-1].end():] if matches else text
    special_match = _SPECIAL_PATTERN.search(tail)
    if special_match:
        already = any(c["number"].startswith("특약") for c in clauses)
        if not already:
            clauses.extend(_split_special(tail[special_match.start():].strip()))


def _split_by_numeric(text: str) -> List[dict]:
    """1. 2. 3. 형태의 숫자 패턴으로 조항을 분리한다."""
    matches = list(_NUMERIC_PATTERN.finditer(text))
    if len(matches) < 2:
        return []

    clauses = []
    for i, match in enumerate(matches):
        number = match.group(1).strip().rstrip(".")
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()

        # 첫 줄이 제목인지 확인 (짧고 마침표 없음)
        lines = body.split("\n")
        if lines and len(lines[0]) < 30 and "." not in lines[0]:
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
        else:
            title = ""

        clauses.append({"number": number, "title": title, "text": body, "items": []})

    return clauses


def _extract_items(text: str) -> List[str]:
    """조항 본문에서 ① ② ③ 항목을 추출한다."""
    if not _ITEM_PATTERN.search(text):
        return []

    # 항 기호 위치로 분리
    parts = _ITEM_PATTERN.split(text)
    markers = _ITEM_PATTERN.findall(text)

    items = []
    for marker, content in zip(markers, parts[1:]):
        item_text = (marker + content.split("\n")[0]).strip()
        if item_text:
            items.append(item_text)

    return items


# ---------------------------------------------------------------------------
# 독립 테스트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    SAMPLE_CONTRACT = """주택 임대차 계약서

임대인(甲): 홍길동 (주민등록번호: 123456-1234567)
임차인(乙): 김철수 (주민등록번호: 234567-2345678)

제1조 (목적)
본 계약은 아래 부동산(이하 "목적물")에 대한 임대차 계약을 체결함을 목적으로 한다.
① 소재지: 서울시 강남구 역삼동 123-45
② 건물종류: 아파트, 전용면적 59㎡

제2조 (임대차 기간)
임대차 기간은 2024년 3월 1일부터 2026년 2월 28일까지로 한다.
① 임차인이 계속 거주를 희망하는 경우 만료 1개월 전에 통보하여야 한다.

제3조 (보증금 및 차임)
① 보증금은 금 일억원정(₩100,000,000)으로 한다.
② 계약금 일천만원은 계약 시 지불하고, 잔금은 입주일에 지불한다.

제4조 (임대인의 의무)
임대인은 임대차 목적물을 임차인이 사용·수익할 수 있도록 유지하여야 한다.
수선 책임은 임대인이 부담하되, 소모성 부품의 교체는 임차인이 부담한다.

제5조 (임차인의 의무)
① 임차인은 임차목적물을 선량한 관리자의 주의로 사용하여야 한다.
② 임차인은 임대인 동의 없이 목적물을 전대하거나 임차권을 양도할 수 없다.
③ 계약 종료 시 원상복구 의무를 진다. 반려동물 사육으로 인한 손상은 임차인 부담이다.

특약사항
1. 임대인은 임대차 기간 중 목적물을 매도할 경우 임차인에게 우선 통보한다.
2. 보증금 반환은 임차인 퇴거 후 3일 이내로 한다. 보증금 반환 거절 시 연 12%의 이자를 가산한다.
3. 흡연은 금지한다.
"""

    print("=== 조항 파서 독립 테스트 ===\n")
    clauses = parse_clauses(SAMPLE_CONTRACT)
    print(f"파싱된 조항 수: {len(clauses)}\n")

    for clause in clauses:
        print(f"[{clause['number']}] {clause['title']}")
        print(f"  본문 (앞 80자): {clause['text'][:80].replace(chr(10), ' ')}")
        if clause["items"]:
            print(f"  항 목록: {clause['items'][:3]}")
        print()

    print("JSON 출력 (첫 2개):")
    print(json.dumps(clauses[:2], ensure_ascii=False, indent=2))
