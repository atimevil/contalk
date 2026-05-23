"""
테스트용 임대차 계약서 PDF 생성 스크립트

실행:
    python tests/contracts/make_contracts.py

생성 파일:
    tests/contracts/계약서_정상형.pdf   — 위험 조항 없는 표준 계약
    tests/contracts/계약서_위험형.pdf   — 다수의 불리한 조항 포함
    tests/contracts/계약서_혼합형.pdf   — 일부 정상 + 일부 위험 조항
    tests/contracts/계약서_특약함정형.pdf — 특약사항에 함정이 숨어있는 계약
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle,
)
from reportlab.lib import colors

OUTPUT_DIR = Path(__file__).parent

# ---------------------------------------------------------------------------
# 폰트 설정 (한글 지원)
# ---------------------------------------------------------------------------

def _register_font() -> str:
    """시스템에서 한글 폰트를 찾아 등록하고 폰트명을 반환한다."""
    candidates = [
        # Windows
        r"C:\Windows\Fonts\malgun.ttf",
        r"C:\Windows\Fonts\gulim.ttc",
        r"C:\Windows\Fonts\batang.ttc",
        # macOS
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/NanumGothic.ttf",
        # Linux
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/unfonts-core/UnDotum.ttf",
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("Korean", path))
                return "Korean"
            except Exception:
                continue

    # 폴백: 기본 폰트 (한글 깨질 수 있음)
    print("경고: 한글 폰트를 찾지 못했습니다. 기본 폰트 사용")
    return "Helvetica"


# ---------------------------------------------------------------------------
# PDF 생성 헬퍼
# ---------------------------------------------------------------------------

def _make_doc(filename: str, font: str) -> tuple:
    path = OUTPUT_DIR / filename
    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=25 * mm,
        rightMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    title_style = ParagraphStyle(
        "Title", fontName=font, fontSize=16, spaceAfter=6,
        alignment=1, textColor=colors.HexColor("#1a1a2e"),
    )
    h1_style = ParagraphStyle(
        "H1", fontName=font, fontSize=11, spaceBefore=10, spaceAfter=4,
        textColor=colors.HexColor("#16213e"), leading=16,
    )
    body_style = ParagraphStyle(
        "Body", fontName=font, fontSize=9, spaceBefore=2, spaceAfter=2,
        leading=14, textColor=colors.HexColor("#333333"),
    )
    small_style = ParagraphStyle(
        "Small", fontName=font, fontSize=8, spaceBefore=1, spaceAfter=1,
        leading=13, textColor=colors.HexColor("#555555"),
    )
    special_style = ParagraphStyle(
        "Special", fontName=font, fontSize=9, spaceBefore=2, spaceAfter=2,
        leading=14, textColor=colors.HexColor("#8b0000"),
        backColor=colors.HexColor("#fff3f3"),
    )
    return doc, path, title_style, h1_style, body_style, small_style, special_style


def _divider(story):
    story.append(Spacer(1, 2 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 2 * mm))


def _build(doc, story):
    doc.build(story)


# ---------------------------------------------------------------------------
# 계약서 1: 정상형 — 표준적이고 임차인에게 불리한 조항이 없는 계약
# ---------------------------------------------------------------------------

def make_safe_contract(font: str):
    doc, path, T, H1, B, S, SP = _make_doc("계약서_정상형.pdf", font)
    story = []

    story.append(Paragraph("주택 임대차 계약서", T))
    story.append(Paragraph("[ 정상 계약 — 표준형 ]", S))
    _divider(story)

    # 당사자
    story.append(Paragraph("■ 계약 당사자", H1))
    data = [
        ["구분", "성명", "주민등록번호", "주소", "연락처"],
        ["임대인(갑)", "홍길동", "650101-1234567", "서울시 강남구 역삼동 123", "010-1234-5678"],
        ["임차인(을)", "김철수", "850515-2345678", "서울시 마포구 합정동 45", "010-9876-5432"],
    ]
    t = Table(data, colWidths=[22*mm, 22*mm, 35*mm, 55*mm, 30*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e8f4f8")),
        ("FONTNAME", (0,0), (-1,-1), font),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(t)
    story.append(Spacer(1, 3*mm))

    # 목적물
    story.append(Paragraph("■ 임대 목적물", H1))
    story.append(Paragraph("소재지: 서울특별시 서초구 반포동 100-5, 반포자이 아파트 101동 1502호", B))
    story.append(Paragraph("건물 종류: 아파트  /  전용 면적: 84.97㎡  /  임대 면적: 전부", B))
    _divider(story)

    articles = [
        ("제1조 (목적)", [
            "본 계약은 위 표시 부동산(이하 '목적물')에 대하여 임대인(이하 '갑')과 임차인(이하 '을') 간에",
            "주택임대차보호법 및 민법의 규정에 따라 임대차 계약을 체결함을 목적으로 한다.",
        ]),
        ("제2조 (임대차 기간)", [
            "임대차 기간은 2024년 7월 1일부터 2026년 6월 30일까지 24개월로 한다.",
            "① 을이 계속 거주를 원하는 경우, 기간 만료 2개월 전까지 갑에게 서면으로 통보하여야 한다.",
            "② 갑이 갱신을 거절하려면 기간 만료 6개월 전부터 2개월 전 사이에 통보하여야 한다.",
        ]),
        ("제3조 (보증금)", [
            "① 보증금은 금 삼억원정(₩300,000,000)으로 한다.",
            "② 계약금 삼천만원은 본 계약 체결 시 지불한다.",
            "③ 잔금 이억칠천만원은 2024년 7월 1일 입주일에 지불하기로 한다.",
            "④ 갑은 을의 퇴거 후 14일 이내에 보증금 전액을 반환하여야 한다.",
        ]),
        ("제4조 (임대인의 의무)", [
            "① 갑은 목적물을 을이 사용·수익할 수 있는 상태로 임대차 기간 동안 유지하여야 한다.",
            "② 갑은 목적물의 구조적 하자 및 주요 설비(보일러, 급·배수관 등)의 수선 의무를 부담한다.",
            "③ 갑은 을에게 사전 통보(48시간 이상) 없이 목적물에 출입할 수 없다.",
        ]),
        ("제5조 (임차인의 의무)", [
            "① 을은 선량한 관리자의 주의로 목적물을 사용하여야 한다.",
            "② 을은 갑의 서면 동의 없이 제3자에게 목적물을 전대할 수 없다.",
            "③ 소모성 부품(전구, 필터 등)의 교체는 을이 부담한다.",
        ]),
        ("제6조 (계약 해지)", [
            "① 을이 3기(月) 이상 차임을 연체하는 경우 갑은 계약을 해지할 수 있다.",
            "② 천재지변 등 불가항력으로 목적물의 사용이 불가능한 경우 양 당사자 합의로 해지할 수 있다.",
        ]),
        ("제7조 (원상복구)", [
            "① 을은 계약 종료 시 목적물을 입주 시 상태로 반환하여야 한다.",
            "② 을의 귀책이 아닌 자연 마모, 경년 변화로 인한 손상은 원상복구 의무에서 제외한다.",
            "③ 원상복구 범위에 대한 분쟁이 발생한 경우 국토교통부 주택임대차분쟁조정위원회의",
            "   조정 기준에 따른다.",
        ]),
        ("제8조 (분쟁 해결)", [
            "① 본 계약에 관한 분쟁은 주택임대차분쟁조정위원회의 조정을 우선 신청할 수 있다.",
            "② 조정이 이루어지지 않는 경우 관할 법원의 판결에 따른다.",
        ]),
    ]

    for title, lines in articles:
        story.append(Paragraph(title, H1))
        for line in lines:
            story.append(Paragraph(line, B))
        story.append(Spacer(1, 2*mm))

    _divider(story)
    story.append(Paragraph("■ 특약사항", H1))
    specials = [
        "1. 갑은 을에게 확정일자 신청 및 전입신고를 적극 협조한다.",
        "2. 갑이 임대차 기간 중 목적물을 매도할 경우 을에게 우선 매수할 기회를 제공한다.",
        "3. 반려동물(소형견 1마리)은 별도 합의로 허용한다.",
    ]
    for s in specials:
        story.append(Paragraph(s, B))

    _divider(story)
    story.append(Paragraph("본 계약서는 2부 작성하여 갑과 을이 각 1부씩 보관한다.", S))
    story.append(Spacer(1, 5*mm))
    story.append(Paragraph("2024년  6월  15일", B))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("임대인(갑):  홍 길 동  (인)", B))
    story.append(Paragraph("임차인(을):  김 철 수  (인)", B))

    _build(doc, story)
    print(f"생성: {path}")


# ---------------------------------------------------------------------------
# 계약서 2: 위험형 — 불리한 조항이 다수 포함
# ---------------------------------------------------------------------------

def make_risky_contract(font: str):
    doc, path, T, H1, B, S, SP = _make_doc("계약서_위험형.pdf", font)
    story = []

    story.append(Paragraph("주택 임대차 계약서", T))
    story.append(Paragraph("[ 주의 — 불리한 조항 다수 포함 ]", ParagraphStyle(
        "Warn", fontName=font, fontSize=10, alignment=1,
        textColor=colors.HexColor("#cc0000"), spaceAfter=4,
    )))
    _divider(story)

    story.append(Paragraph("■ 계약 당사자", H1))
    data = [
        ["구분", "성명", "주소", "연락처"],
        ["임대인(갑)", "이기심", "서울시 강남구 청담동 777", "010-0000-1111"],
        ["임차인(을)", "박피해", "미정", "010-2222-3333"],
    ]
    t = Table(data, colWidths=[22*mm, 30*mm, 75*mm, 35*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#fce8e8")),
        ("FONTNAME", (0,0), (-1,-1), font),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
    ]))
    story.append(t)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("■ 임대 목적물", H1))
    story.append(Paragraph("소재지: 서울특별시 관악구 신림동 99-1, 신림오피스텔 305호", B))
    story.append(Paragraph("건물 종류: 오피스텔  /  전용 면적: 33.05㎡", B))
    _divider(story)

    articles = [
        ("제1조 (목적)", [
            "본 계약은 위 표시 목적물에 대한 임대차 계약을 체결함을 목적으로 한다.",
        ]),
        ("제2조 (임대차 기간)", [
            "임대차 기간은 2024년 8월 1일부터 2025년 7월 31일까지 12개월로 한다.",
            "① 갑은 필요에 따라 계약 기간을 일방적으로 단축할 수 있으며, 을은 이에 이의를 제기할 수 없다.",
        ]),
        ("제3조 (보증금 및 차임)", [
            "① 보증금은 금 오천만원정(₩50,000,000)으로 한다.",
            "② 월 차임은 금 팔십만원정으로 매월 5일까지 선불로 지급하여야 한다.",
            "③ 을이 월 차임을 기일 내 납부하지 않는 경우 연체 이자 연 24%를 가산한다.",
            "④ 보증금에는 이자가 발생하지 않으며, 갑은 이에 대해 어떠한 이자도 지급하지 않는다.",
        ]),
        ("제4조 (임대인의 출입)", [
            "갑 또는 갑이 지정한 자는 언제든지 목적물에 방문 및 출입할 수 있으며,",
            "을은 이에 대해 거부하거나 이의를 제기할 수 없다.",
        ]),
        ("제5조 (수선 및 관리)", [
            "① 수선 책임은 소모성 부품을 포함한 모든 수선 비용에 대해 을이 전액 부담한다.",
            "② 보일러, 급수관, 배수관 등 설비의 수리 비용도 을의 부담으로 한다.",
            "③ 관리비는 공용 관리비를 포함하여 을이 전액 부담한다.",
        ]),
        ("제6조 (임차인의 의무)", [
            "① 을은 갑의 서면 동의 없이 목적물을 전대하거나 임차권을 양도할 수 없다.",
            "② 임차권 등기 신청 금지: 을은 어떠한 경우에도 임차권 등기를 신청할 수 없다.",
            "③ 확정일자 신청 금지: 을은 전입신고 및 확정일자 신청을 하여서는 아니 된다.",
            "④ 을은 대항력 포기에 동의한다.",
        ]),
        ("제7조 (계약 해지)", [
            "① 갑은 사업상 필요 등 갑이 판단하는 사유가 있으면 언제든지 계약을 해지할 수 있다.",
            "② 을이 계약을 중도해지하는 경우 위약금으로 보증금의 10%를 갑에게 지급하여야 한다.",
            "③ 계약 해지 불가: 을은 임대차 기간 중 어떠한 사유로도 계약을 해지할 수 없다.",
        ]),
        ("제8조 (원상복구)", [
            "① 을은 계약 종료 시 목적물 일체를 입주 당시 상태로 원상복구하여야 한다.",
            "② 원상복구 범위는 갑이 단독으로 결정하며, 을은 이에 따라야 한다.",
            "③ 원상복구 비용이 보증금을 초과하는 경우 을은 그 초과분을 즉시 지급하여야 한다.",
        ]),
        ("제9조 (보증금 반환)", [
            "갑은 을의 퇴거 후 보증금 반환 시기를 갑이 단독으로 결정하며,",
            "보증금 반환 거절 시에도 을은 이에 대해 법적 이의를 제기할 수 없다.",
            "보증금에서 일방적으로 수선비·관리비·원상복구비를 공제한 후 잔액을 반환한다.",
        ]),
    ]

    for title, lines in articles:
        story.append(Paragraph(title, H1))
        for line in lines:
            story.append(Paragraph(line, B))
        story.append(Spacer(1, 2*mm))

    _divider(story)
    story.append(Paragraph("■ 특약사항", H1))
    specials = [
        "1. 반려동물 사육 금지, 흡연 금지, 악기 연주 금지.",
        "2. 인테리어 변경 및 시설 개조 공사 금지.",
        "3. 에어컨, 세탁기 추가 설치 금지.",
        "4. 전입신고 금지 (갑의 세금 문제로 인해 전입신고를 하여서는 아니 된다).",
        "5. 을은 주택임대차보호법상 일체의 권리를 포기하기로 합의한다.",
        "6. 임대인은 언제든지 사전 통보 없이 출입할 수 있으며 을은 거부할 수 없다.",
    ]
    for s in specials:
        story.append(Paragraph(s, B))

    _divider(story)
    story.append(Paragraph("2024년  7월  1일", B))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("임대인(갑):  이 기 심  (인)", B))
    story.append(Paragraph("임차인(을):  박 피 해  (인)", B))

    _build(doc, story)
    print(f"생성: {path}")


# ---------------------------------------------------------------------------
# 계약서 3: 혼합형 — 일부 정상 조항 + 일부 문제 조항
# ---------------------------------------------------------------------------

def make_mixed_contract(font: str):
    doc, path, T, H1, B, S, SP = _make_doc("계약서_혼합형.pdf", font)
    story = []

    story.append(Paragraph("주택 임대차 계약서", T))
    story.append(Paragraph("[ 혼합형 — 일부 조항 검토 필요 ]", S))
    _divider(story)

    story.append(Paragraph("■ 계약 당사자", H1))
    data = [
        ["구분", "성명", "주소", "연락처"],
        ["임대인(갑)", "최집주", "서울시 송파구 잠실동 200", "010-5555-6666"],
        ["임차인(을)", "정세입", "서울시 광진구 자양동 88", "010-7777-8888"],
    ]
    t = Table(data, colWidths=[22*mm, 30*mm, 75*mm, 35*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#f0f0e8")),
        ("FONTNAME", (0,0), (-1,-1), font),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
    ]))
    story.append(t)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("■ 임대 목적물", H1))
    story.append(Paragraph("소재지: 서울특별시 송파구 신천동 7-1, 잠실파크리오 206동 801호", B))
    story.append(Paragraph("건물 종류: 아파트  /  전용 면적: 59.99㎡", B))
    _divider(story)

    articles = [
        ("제1조 (목적)", [
            "본 계약은 위 표시 부동산에 대한 임대차 계약을 목적으로 한다.",
        ]),
        ("제2조 (임대차 기간)", [
            "임대차 기간은 2024년 9월 1일부터 2026년 8월 31일까지 24개월로 한다.",
            "① 을이 계속 거주를 희망하는 경우 기간 만료 2개월 전까지 통보하여야 한다.",
        ]),
        ("제3조 (보증금)", [
            "① 보증금은 금 이억원정(₩200,000,000)으로 한다.",
            "② 계약금 이천만원은 계약 체결 시, 잔금은 입주일에 지불한다.",
            "③ 보증금 반환은 을의 퇴거 완료 후 30일 이내로 한다.",
        ]),
        ("제4조 (임대인의 의무)", [
            "갑은 목적물을 을이 사용·수익할 수 있는 상태로 유지하여야 한다.",
            "다만, 갑은 언제든지 사전 통보 없이 목적물에 출입할 수 있다.",  # 문제 조항
        ]),
        ("제5조 (임차인의 의무)", [
            "① 을은 선량한 관리자의 주의로 목적물을 사용하여야 한다.",
            "② 을은 갑의 서면 동의 없이 임차권을 양도하거나 목적물을 전대할 수 없다.",
            "③ 수선 책임 및 수선 비용은 소모성 부품을 포함하여 을이 부담한다.",  # 문제 조항
            "④ 계약 종료 시 원상복구 의무를 부담한다.",  # 주의 필요
        ]),
        ("제6조 (차임 및 연체)", [
            "① 월 차임은 없는 전세 계약으로 한다.",
            "② 관리비는 실비 정산하며 을이 부담한다.",
        ]),
        ("제7조 (계약 해지)", [
            "① 을이 2기(月) 이상 관리비를 납부하지 않는 경우 갑은 계약을 해지할 수 있다.",
            "② 을의 중도 해지 시 위약금으로 보증금의 5%를 갑에게 지급하여야 한다.",
        ]),
    ]

    for title, lines in articles:
        story.append(Paragraph(title, H1))
        for line in lines:
            story.append(Paragraph(line, B))
        story.append(Spacer(1, 2*mm))

    _divider(story)
    story.append(Paragraph("■ 특약사항", H1))
    specials = [
        "1. 반려동물 사육 금지.",
        "2. 흡연은 실내 전 구역 금지로 한다.",
        "3. 갑은 임대차 기간 중 목적물 매도 시 을에게 사전 통보한다.",
        "4. 을의 확정일자 신청 및 전입신고에 갑은 적극 협조한다.",
        "5. 에어컨 추가 설치는 갑의 사전 동의를 받아야 한다.",
    ]
    for s in specials:
        story.append(Paragraph(s, B))

    _divider(story)
    story.append(Paragraph("2024년  8월  20일", B))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("임대인(갑):  최 집 주  (인)", B))
    story.append(Paragraph("임차인(을):  정 세 입  (인)", B))

    _build(doc, story)
    print(f"생성: {path}")


# ---------------------------------------------------------------------------
# 계약서 4: 특약함정형 — 본 조항은 무난하지만 특약에 함정
# ---------------------------------------------------------------------------

def make_trap_special_contract(font: str):
    doc, path, T, H1, B, S, SP = _make_doc("계약서_특약함정형.pdf", font)
    story = []

    story.append(Paragraph("주택 임대차 계약서", T))
    story.append(Paragraph("[ 특약사항 주의 — 본문은 무난, 특약에 불리한 조항 ]", S))
    _divider(story)

    story.append(Paragraph("■ 계약 당사자", H1))
    data = [
        ["구분", "성명", "주소", "연락처"],
        ["임대인(갑)", "강속임", "서울시 용산구 이태원동 333", "010-3333-4444"],
        ["임차인(을)", "윤모름", "서울시 동작구 사당동 55", "010-9999-0000"],
    ]
    t = Table(data, colWidths=[22*mm, 30*mm, 75*mm, 35*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e8f0e8")),
        ("FONTNAME", (0,0), (-1,-1), font),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("GRID", (0,0), (-1,-1), 0.5, colors.grey),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
    ]))
    story.append(t)
    story.append(Spacer(1, 3*mm))

    story.append(Paragraph("■ 임대 목적물", H1))
    story.append(Paragraph("소재지: 서울특별시 용산구 한남동 150-3, 한남더힐 B동 701호", B))
    story.append(Paragraph("건물 종류: 아파트  /  전용 면적: 114.05㎡", B))
    _divider(story)

    articles = [
        ("제1조 (목적)", [
            "본 계약은 위 표시 부동산에 대한 임대차 계약을 목적으로 한다.",
        ]),
        ("제2조 (임대차 기간)", [
            "임대차 기간은 2024년 10월 1일부터 2026년 9월 30일까지 24개월로 한다.",
            "① 기간 만료 전 재계약을 원하는 경우 2개월 전 통보하여야 한다.",
        ]),
        ("제3조 (보증금)", [
            "① 보증금은 금 오억원정(₩500,000,000)으로 한다.",
            "② 계약금 오천만원은 계약 체결 시 지불하고, 잔금은 입주일에 지불한다.",
            "③ 보증금 반환은 을의 퇴거 후 14일 이내로 한다.",
        ]),
        ("제4조 (임대인의 의무)", [
            "① 갑은 목적물을 임대차 기간 동안 정상 사용할 수 있는 상태로 유지한다.",
            "② 갑은 을에게 사전 통보 후 목적물에 출입할 수 있다.",
        ]),
        ("제5조 (임차인의 의무)", [
            "① 을은 선량한 관리자의 주의로 목적물을 사용하여야 한다.",
            "② 을은 갑의 동의 없이 임차권을 제3자에게 양도하거나 전대할 수 없다.",
            "③ 소모성 부품의 교체는 을이 부담한다.",
            "④ 계약 종료 시 자연 마모를 제외한 원상복구 의무를 부담한다.",
        ]),
        ("제6조 (계약 해지)", [
            "① 을이 3기 이상 차임을 연체하거나 갑에게 중대한 손해를 발생시키는 경우 갑은 해지할 수 있다.",
        ]),
    ]

    for title, lines in articles:
        story.append(Paragraph(title, H1))
        for line in lines:
            story.append(Paragraph(line, B))
        story.append(Spacer(1, 2*mm))

    _divider(story)
    story.append(Paragraph("■ 특약사항  ★ 아래 내용을 반드시 확인하세요 ★", H1))
    specials = [
        "1. 을은 전입신고 금지. 갑의 금융 거래상 이유로 전입신고를 하여서는 아니 된다.",
        "2. 확정일자 신청 금지 및 임차권 등기 신청 금지에 을이 동의함.",
        "3. 을은 대항력 포기를 확인하며 이와 관련한 일체의 법적 권리를 주장하지 않는다.",
        "4. 보증금 반환 거절 시에도 을은 법적 이의를 제기하지 않기로 한다.",
        "5. 갑은 임대차 기간 중 언제든지 목적물을 경매·공매에 부칠 수 있으며 을은 이의를 제기할 수 없다.",
        "6. 반려동물 사육 금지, 흡연 금지, 외국인 동거 금지.",
        "7. 갑의 동의 없는 인테리어 변경 금지. 시설 구조 변경 공사 금지.",
        "8. 에어컨 추가 설치 금지, 세탁기 드럼형으로만 사용 가능.",
    ]
    for s in specials:
        story.append(Paragraph(s, B))

    _divider(story)
    story.append(Paragraph("2024년  9월  15일", B))
    story.append(Spacer(1, 8*mm))
    story.append(Paragraph("임대인(갑):  강 속 임  (인)", B))
    story.append(Paragraph("임차인(을):  윤 모 름  (인)", B))

    _build(doc, story)
    print(f"생성: {path}")


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    font = _register_font()
    print(f"사용 폰트: {font}\n")

    make_safe_contract(font)
    make_risky_contract(font)
    make_mixed_contract(font)
    make_trap_special_contract(font)

    print("\n완료! tests/contracts/ 폴더에서 확인하세요.")
    print("\n예상 분석 결과:")
    print("  계약서_정상형.pdf    → safe 위주, 큰 문제 없음")
    print("  계약서_위험형.pdf    → medium 다수 (대항력 포기, 확정일자 금지 등)")
    print("  계약서_혼합형.pdf    → medium + caution 혼재")
    print("  계약서_특약함정형.pdf → 본문 safe, 특약에 medium 집중")
