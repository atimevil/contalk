"""
계약똑똑 테스트용 임대차 계약서 4종 생성기

1. contract_01_jeonse_danger.pdf   전세 — 위험 조항 다수 (악성 집주인)
2. contract_02_jeonse_normal.pdf   전세 — 표준 계약 (약간의 주의 조항)
3. contract_03_monthly_medium.pdf  월세 — 중간 위험 (수선비·관리비 이슈)
4. contract_04_jeonse_safe.pdf     전세 — 우량 계약 (임차인 보호 특약 완비)
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
import os, sys

# 스크립트 위치 기준으로 PDF 출력 (어디서 실행하든 이 파일 옆에 생성)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── 폰트 ──────────────────────────────────────────────────────────────────────
FONT_PATHS = [
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]
font_path = next((p for p in FONT_PATHS if os.path.exists(p)), None)
if not font_path:
    sys.exit("❌ 한글 폰트 없음")
pdfmetrics.registerFont(TTFont("KR",   font_path))
pdfmetrics.registerFont(TTFont("KR-B", font_path))   # bold 대용
print(f"폰트: {font_path}")

W, H  = A4
LM    = 18 * mm   # left margin
RM    = W - 18*mm # right edge
TM    = H - 18*mm # top
BM    = 22 * mm   # bottom

# ── 공통 유틸 ─────────────────────────────────────────────────────────────────

def new_doc(filename):
    c = canvas.Canvas(filename, pagesize=A4)
    return c

def title_block(c, title, subtitle="주택임대차계약서"):
    """상단 제목 블록"""
    # 배경 헤더바
    c.setFillColorRGB(0.08, 0.35, 0.72)
    c.rect(LM, TM - 22*mm, RM - LM, 20*mm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("KR-B", 15)
    c.drawCentredString(W/2, TM - 10*mm, subtitle)
    c.setFont("KR", 9)
    c.drawCentredString(W/2, TM - 16*mm, title)
    c.setFillColorRGB(0, 0, 0)
    return TM - 26*mm  # next y

LINE_H  = 6.5 * mm   # 본문 줄 간격
SEC_H   = 7.5 * mm   # 섹션 제목 줄 간격
GAP     = 3   * mm   # 섹션 앞 여백

def draw_table(c, y, data, col_widths, row_height=8*mm, header_row=True):
    """간단한 표 그리기"""
    x0 = LM
    for r, row in enumerate(data):
        x = x0
        for ci, (cell, cw) in enumerate(zip(row, col_widths)):
            if r == 0 and header_row:
                c.setFillColorRGB(0.88, 0.92, 0.98)
            elif ci == 0:
                c.setFillColorRGB(0.95, 0.95, 0.95)
            else:
                c.setFillColorRGB(1, 1, 1)
            c.rect(x, y - row_height, cw, row_height, fill=1, stroke=1)
            c.setFillColorRGB(0, 0, 0)
            font_size = 8.5 if (r == 0 and header_row) else 9
            c.setFont("KR-B" if (r == 0 and header_row) else "KR", font_size)
            # 텍스트를 셀 수직 중앙에 배치
            c.drawString(x + 2.5*mm, y - row_height + 2.8*mm, str(cell))
            x += cw
        y -= row_height
    return y - 2*mm

def section(c, y, text):
    """조항 제목 — 앞에 여백 추가"""
    y -= GAP
    if y < BM + 15*mm:
        c.showPage()
        y = TM - 5*mm
    c.setFont("KR-B", 10)
    c.setFillColorRGB(0.08, 0.35, 0.72)
    c.drawString(LM, y, text)
    c.setFillColorRGB(0, 0, 0)
    return y - SEC_H

def body(c, y, text, indent=0, size=9):
    """본문 텍스트"""
    if y < BM + 12*mm:
        c.showPage()
        y = TM - 5*mm
    c.setFont("KR", size)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(LM + indent*mm, y, text)
    return y - LINE_H

def stamp_circle(c, x, y, r=7*mm, color=(0.8,0.1,0.1)):
    """도장 원"""
    c.setStrokeColorRGB(*color)
    c.setLineWidth(1.5)
    c.circle(x, y, r, stroke=1, fill=0)
    c.setFont("KR", 5.5)
    c.setFillColorRGB(*color)
    c.drawCentredString(x, y - 1.5*mm, "인")
    c.setFillColorRGB(0,0,0)
    c.setLineWidth(0.5)

def sign_block(c, y, landlord, tenant, agent_name="(주)믿음공인중개사", agent_reg="11-가-00123"):
    """서명란"""
    # 여백이 부족하면 새 페이지
    if y < BM + 60*mm:
        c.showPage()
        y = TM - 5*mm

    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(LM, y, RM, y)
    y -= 6*mm
    c.setFont("KR-B", 9.5)
    c.setFillColorRGB(0.08, 0.35, 0.72)
    c.drawString(LM, y, "【계약당사자 확인 및 서명】")
    c.setFillColorRGB(0, 0, 0)
    y -= 9*mm

    # 임대인 / 임차인 2열
    col  = (RM - LM) / 2
    row_gap = 6.5*mm
    for i, (label, info) in enumerate([(f"임 대 인", landlord), (f"임 차 인", tenant)]):
        cx  = LM + i * col
        ty  = y
        c.setFont("KR-B", 9)
        c.drawString(cx, ty, label)
        ty -= row_gap
        c.setFont("KR", 8.5)
        for line in info:
            c.drawString(cx + 2*mm, ty, line)
            ty -= row_gap
        stamp_circle(c, cx + col - 14*mm, y - row_gap)
    y -= (len(landlord) + 2) * row_gap

    # 공인중개사
    y -= 4*mm
    c.setStrokeColorRGB(0.85, 0.85, 0.85)
    c.line(LM, y + 2*mm, RM, y + 2*mm)
    c.setFont("KR-B", 9)
    c.drawString(LM, y, "개업공인중개사")
    y -= row_gap
    c.setFont("KR", 8.5)
    for line in [f"상    호: {agent_name}", f"등록번호: {agent_reg}",
                 "소 재 지: 서울특별시 노원구 상계로 45, 1층"]:
        c.drawString(LM + 2*mm, y, line)
        y -= row_gap
    stamp_circle(c, RM - 14*mm, y + row_gap * 1.5)
    return y

def footer(c):
    c.setFont("KR", 7)
    c.setFillColorRGB(0.5,0.5,0.5)
    c.drawCentredString(W/2, BM - 5*mm,
        "본 계약서는 계약똑똑 AI 분석 테스트용으로 작성된 샘플입니다.")
    c.setFillColorRGB(0,0,0)

# ══════════════════════════════════════════════════════════════════════════════
# 계약서 1: 전세 — 위험 조항 다수 (악성 집주인)
# ══════════════════════════════════════════════════════════════════════════════
def make_contract_01():
    fname = "contract_01_jeonse_danger.pdf"
    c = new_doc(fname)
    y = title_block(c, "【위험 조항 다수 — 임차인 불리 계약】", "주택 전세 임대차 계약서")

    y -= 3*mm
    # 부동산 표시
    c.setFont("KR-B", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "서울특별시 노원구 상계동 123-45, 현대4차아파트 101동 502호"],
        ["면    적", "전용면적 84.73 ㎡  /  공급면적 107.59 ㎡"],
        ["구    조", "철근콘크리트조 아파트"],
    ], [30*mm, RM-LM-30*mm], row_height=6.5*mm)

    y -= 2*mm
    c.setFont("KR-B", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["전세 보증금", "금 이억오천만원정  (₩ 250,000,000)"],
        ["계  약  금", "금 이천오백만원정  (₩ 25,000,000)  — 계약 시 지급"],
        ["잔    금", "금 이억이천오백만원정  (₩ 225,000,000)  — 2025년 06월 30일"],
        ["임대 기간", "2025년 07월 01일  ~  2027년 06월 30일  (24개월)"],
    ], [40*mm, RM-LM-40*mm], row_height=6.5*mm)

    y -= 4*mm
    y = section(c, y, "제1조 (목적)")
    y = body(c, y, "본 계약은 위 표시 부동산에 대한 임대차 계약을 체결함을 목적으로 한다.")

    y = section(c, y, "제2조 (임대차 기간)")
    y = body(c, y, "임대차 기간은 2025년 7월 1일부터 2027년 6월 30일까지 24개월로 한다.")

    y = section(c, y, "제3조 (사용 제한 및 금지사항)")
    y = body(c, y, "① 임차인은 임대인의 서면 동의 없이 목적물을 전대하거나 임차권을 제3자에게 양도할 수 없다.")
    y = body(c, y, "② 반려동물 및 애완동물 사육을 금지한다.")
    y = body(c, y, "③ 건물 내외 흡연을 금지한다.")
    y = body(c, y, "④ 임차인은 에어컨, 세탁기 등 설치를 임대인 사전 동의 없이 설치 금지한다.")

    y = section(c, y, "제4조 (수선 및 관리 책임)")
    y = body(c, y, "목적물의 수선 책임 및 비용은 천재지변을 포함한 모든 사유에 대해 임차인이 전액 부담한다.")

    y = section(c, y, "제5조 (원상복구)")
    y = body(c, y, "계약 종료 시 임차인은 목적물을 입주 당시 상태로 원상복구하여야 하며,")
    y = body(c, y, "원상복구 비용은 임차인이 전액 부담한다. 복구 미이행 시 보증금에서 공제한다.")

    y = section(c, y, "제6조 (관리비)")
    y = body(c, y, "관리비 전액은 임차인이 부담하며, 2개월 이상 미납 시 임대인은 보증금에서 우선 공제할 수 있다.")

    y = section(c, y, "제7조 (임대인의 출입)")
    y = body(c, y, "임대인은 목적물의 유지·관리·점검을 위해 언제든지 사전 통보 없이 방문 및 출입할 수 있으며,")
    y = body(c, y, "임차인은 이를 거부할 수 없다.")

    y = section(c, y, "제8조 (계약 해지)")
    y = body(c, y, "① 임차인은 임의로 계약을 해지할 수 없다.")
    y = body(c, y, "② 임대인은 필요 시 언제든지 일방적으로 계약을 해지할 수 있으며, 임차인은 통보 후 14일 이내 퇴거한다.")
    y = body(c, y, "③ 임차인의 사정으로 중도 해지 시 보증금의 10%를 위약금으로 임대인에게 지급하여야 한다.")

    y = section(c, y, "제9조 (연체 이자)")
    y = body(c, y, "임차인이 차임 또는 공과금을 1회 이상 연체할 경우 연체 이율 연 20%의 지연이자를 가산하며,")
    y = body(c, y, "임대인은 즉시 계약 해지 및 퇴거를 요구할 수 있다.")

    y = section(c, y, "제10조 (보증금 반환)")
    y = body(c, y, "① 임대인은 원상복구 완료 확인 후 60일 이내에 보증금을 반환한다.")
    y = body(c, y, "② 임차인의 채무 불이행이 있는 경우 임대인은 보증금 반환을 거절할 수 있다.")
    y = body(c, y, "③ 보증금에 대한 이자는 발생하지 아니하며 임대인은 이를 지급하지 아니한다.")
    y = body(c, y, "④ 임차인의 임차권 등기 신청을 금지한다.")

    y -= 3*mm
    c.setFont("KR-B", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【특약사항】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    specials = [
        "1. 임차인은 전입신고를 임대인 동의 없이 할 수 없다.",
        "2. 확정일자 신청은 임대인의 동의를 요한다.",
        "3. 대항력 취득을 포기한다.",
        "4. 임대인의 매도 시 임차인은 즉시 퇴거에 동의한다.",
        "5. 본 계약서에 날인함으로써 상기 모든 조항에 동의한 것으로 본다.",
    ]
    for s in specials:
        y = body(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년  6월   일  계약을 체결한다.")
    y -= 8*mm

    sign_block(c, y,
        landlord=["성  명: 홍 길 동", "주  소: 서울시 강남구 테헤란로 100", "연락처: 010-1234-5678"],
        tenant= ["성  명: 김 철 수", "주  소: 서울시 노원구 상계동 456", "연락처: 010-9876-5432"],
    )
    footer(c)
    c.save()
    print(f"✅ {fname}")


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 2: 전세 — 표준 계약 (약간의 주의 조항)
# ══════════════════════════════════════════════════════════════════════════════
def make_contract_02():
    fname = "contract_02_jeonse_normal.pdf"
    c = new_doc(fname)
    y = title_block(c, "【표준 전세 계약 — 일부 주의 조항 포함】", "주택 전세 임대차 계약서")

    y -= 3*mm
    c.setFont("KR-B", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "서울특별시 마포구 합정동 567, 래미안합정리버스 203동 1201호"],
        ["면    적", "전용면적 59.97 ㎡"],
        ["구    조", "철근콘크리트조 아파트"],
    ], [30*mm, RM-LM-30*mm], row_height=6.5*mm)

    y -= 2*mm
    c.setFont("KR-B", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["전세 보증금", "금 사억오천만원정  (₩ 450,000,000)"],
        ["계  약  금", "금 사천오백만원정  (₩ 45,000,000)  — 계약 시 지급"],
        ["잔    금", "금 사억오백만원정  (₩ 405,000,000)  — 2025년 09월 30일"],
        ["임대 기간", "2025년 10월 01일  ~  2027년 09월 30일  (24개월)"],
    ], [40*mm, RM-LM-40*mm], row_height=6.5*mm)

    y -= 4*mm
    y = section(c, y, "제1조 (목적)")
    y = body(c, y, "본 계약은 위 표시 부동산에 대한 임대차 계약을 체결함을 목적으로 한다.")

    y = section(c, y, "제2조 (임대차 기간)")
    y = body(c, y, "임대차 기간은 2025년 10월 1일부터 2027년 9월 30일까지 24개월로 한다.")
    y = body(c, y, "기간 만료 시 임대인 또는 임차인은 2개월 전까지 갱신 거절 의사를 상대방에게 통보하여야 한다.")

    y = section(c, y, "제3조 (사용 목적)")
    y = body(c, y, "임차인은 목적물을 주거 목적으로만 사용하여야 하며, 임대인 동의 없이 전대할 수 없다.")
    y = body(c, y, "반려동물 사육은 임대인의 사전 서면 동의 후 허용된다.")

    y = section(c, y, "제4조 (수선의무)")
    y = body(c, y, "임대인은 목적물을 사용·수익에 필요한 상태로 유지할 의무를 진다.")
    y = body(c, y, "단, 임차인의 고의 또는 과실로 인한 파손은 임차인이 비용을 부담한다.")
    y = body(c, y, "소모성 부품(전구, 배수구 등) 교체는 임차인이 부담한다.")

    y = section(c, y, "제5조 (원상복구)")
    y = body(c, y, "계약 종료 시 임차인은 목적물을 원상복구하여야 하나,")
    y = body(c, y, "통상적인 사용에 의한 마모·손상은 임차인의 원상복구 의무에서 제외한다.")

    y = section(c, y, "제6조 (관리비)")
    y = body(c, y, "관리비는 임차인이 부담하되, 임대인이 부담할 항목은 별도 협의한다.")

    y = section(c, y, "제7조 (임대인의 출입)")
    y = body(c, y, "임대인은 목적물 점검 시 임차인에게 24시간 전 사전 통보 후 방문할 수 있다.")

    y = section(c, y, "제8조 (계약 해지)")
    y = body(c, y, "① 임차인이 차임을 3기 이상 연체하거나 임대차 목적에 현저히 반하는 사용 시 임대인은 해지할 수 있다.")
    y = body(c, y, "② 임차인이 중도 해지 시 임대인은 신규 임차인을 구할 때까지 발생하는 손해를 청구할 수 있다.")

    y = section(c, y, "제9조 (보증금 반환)")
    y = body(c, y, "① 임대인은 계약 종료 및 임차인의 퇴거 후 14일 이내에 보증금을 반환한다.")
    y = body(c, y, "② 보증금 반환 지연 시 연 5%의 지연이자를 가산한다.")

    y = section(c, y, "제10조 (대항력 및 우선변제)")
    y = body(c, y, "임차인은 전입신고 및 확정일자를 자유롭게 신청할 수 있다.")

    y -= 3*mm
    c.setFont("KR-B", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【특약사항】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    specials = [
        "1. 임대인은 계약 체결 전 등기부등본을 임차인에게 제시하였음을 확인한다.",
        "2. 현 시설물 상태로 임대하며, 입주 전 하자 부분은 임대인이 보수한다.",
        "3. 흡연은 실외 지정 구역에서만 허용한다.",
        "4. 인테리어 변경 시 원상복구를 조건으로 임대인의 서면 동의 후 가능하다.",
        "5. 임차인의 계약갱신요구권 행사를 임대인은 정당한 사유 없이 거부할 수 없다.",
    ]
    for s in specials:
        y = body(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년  9월   일  계약을 체결한다.")
    y -= 8*mm

    sign_block(c, y,
        landlord=["성  명: 이 영 자", "주  소: 경기도 성남시 분당구 야탑동 789", "연락처: 010-2345-6789"],
        tenant= ["성  명: 박 민 준", "주  소: 서울시 성동구 행당동 100", "연락처: 010-8765-4321"],
        agent_name="(주)합정부동산", agent_reg="04-나-00456",
    )
    footer(c)
    c.save()
    print(f"✅ {fname}")


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 3: 월세 — 중간 위험 (수선비·관리비 이슈)
# ══════════════════════════════════════════════════════════════════════════════
def make_contract_03():
    fname = "contract_03_monthly_medium.pdf"
    c = new_doc(fname)
    y = title_block(c, "【월세 계약 — 중간 위험 조항 포함】", "주택 월세 임대차 계약서")

    y -= 3*mm
    c.setFont("KR-B", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "서울특별시 관악구 신림동 888-12, 신림파크빌 302호"],
        ["면    적", "전용면적 33.05 ㎡  (다세대주택)"],
        ["구    조", "철근콘크리트조 다세대"],
    ], [30*mm, RM-LM-30*mm], row_height=6.5*mm)

    y -= 2*mm
    c.setFont("KR-B", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["보  증  금", "금 오천만원정  (₩ 50,000,000)"],
        ["월    세", "금 육십만원정  (₩ 600,000) — 매월 10일 선불"],
        ["계  약  금", "금 오백만원정  (₩ 5,000,000)  — 계약 시 지급"],
        ["잔    금", "금 사천오백만원정  (₩ 45,000,000)  — 2025년 07월 31일"],
        ["임대 기간", "2025년 08월 01일  ~  2026년 07월 31일  (12개월)"],
        ["관  리  비", "월 80,000원 (냉·난방비 별도)"],
    ], [40*mm, RM-LM-40*mm], row_height=6.5*mm)

    y -= 4*mm
    y = section(c, y, "제1조 (목적)")
    y = body(c, y, "본 계약은 위 표시 부동산에 대한 월세 임대차 계약을 체결함을 목적으로 한다.")

    y = section(c, y, "제2조 (임대차 기간)")
    y = body(c, y, "임대차 기간은 2025년 8월 1일부터 2026년 7월 31일까지 12개월로 한다.")

    y = section(c, y, "제3조 (차임 지급)")
    y = body(c, y, "임차인은 매월 10일까지 차임을 임대인 계좌(국민은행 123-456-789012 이영자)로 지급한다.")
    y = body(c, y, "차임이 지정일을 초과하여 지급될 경우 연체로 간주한다.")

    y = section(c, y, "제4조 (연체 및 해지)")
    y = body(c, y, "① 임차인이 차임을 2회 이상 연체할 경우 임대인은 계약을 즉시 해지할 수 있다.")
    y = body(c, y, "② 연체 차임에 대해서는 연체 이율 연 15%의 지연이자를 가산한다.")

    y = section(c, y, "제5조 (수선 의무)")
    y = body(c, y, "수선 책임 및 비용은 임차인이 부담한다. 단, 임대인의 귀책에 의한 구조적 하자는 임대인이 부담한다.")

    y = section(c, y, "제6조 (관리비)")
    y = body(c, y, "관리비 전액은 임차인 부담이며, 미납 시 임대인은 보증금에서 우선 공제할 수 있다.")
    y = body(c, y, "냉·난방비, 주차비 등 개별 사용요금은 실사용량에 따라 별도 부담한다.")

    y = section(c, y, "제7조 (원상복구)")
    y = body(c, y, "임차인은 계약 종료 시 목적물을 원상복구하여야 하며,")
    y = body(c, y, "자연 노후화에 의한 손상도 임차인이 복구할 의무를 진다.")

    y = section(c, y, "제8조 (사용 제한)")
    y = body(c, y, "① 전대 및 임차권 양도를 금지한다.")
    y = body(c, y, "② 반려동물 사육을 금지한다.")
    y = body(c, y, "③ 흡연을 금지한다.")
    y = body(c, y, "④ 심야 시간대(22:00 이후) 소음 발생을 금지한다.")

    y = section(c, y, "제9조 (보증금 반환)")
    y = body(c, y, "임대인은 임차인의 원상복구 완료 및 관리비 정산 확인 후 30일 이내에 보증금을 반환한다.")
    y = body(c, y, "임차인의 미납 채무가 있는 경우 보증금에서 공제 후 반환할 수 있다.")

    y = section(c, y, "제10조 (중도 해지)")
    y = body(c, y, "임차인이 기간 만료 전 계약을 해지할 경우 잔여 임대료 2개월분을 위약금으로 지급한다.")

    y -= 3*mm
    c.setFont("KR-B", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【특약사항】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    specials = [
        "1. 에어컨 1대는 임대인 소유이며 고장 시 임대인이 수리한다.",
        "2. 보일러 고장 시 수리비는 임차인이 부담한다.",
        "3. 인테리어·벽지 도배 등 시설 변경은 금지한다.",
        "4. 주차 공간 1대 제공, 추가 차량은 별도 월 50,000원 협의.",
        "5. 계약 만료 전 이사 시 신규 임차인 소개 의무가 있다.",
    ]
    for s in specials:
        y = body(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년  7월   일  계약을 체결한다.")
    y -= 8*mm

    sign_block(c, y,
        landlord=["성  명: 정 순 희", "주  소: 경기도 안양시 동안구 호계동 200", "연락처: 010-3456-7890"],
        tenant= ["성  명: 최 지 연", "주  소: 서울시 관악구 신림동 100", "연락처: 010-7654-3210"],
        agent_name="신림공인중개사", agent_reg="21-다-00789",
    )
    footer(c)
    c.save()
    print(f"✅ {fname}")


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 4: 전세 — 우량 계약 (임차인 보호 특약 완비)
# ══════════════════════════════════════════════════════════════════════════════
def make_contract_04():
    fname = "contract_04_jeonse_safe.pdf"
    c = new_doc(fname)
    y = title_block(c, "【임차인 보호 특약 완비 — 표준 우량 계약】", "주택 전세 임대차 계약서")

    y -= 3*mm
    c.setFont("KR-B", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "서울특별시 송파구 잠실동 10-5, 잠실파크리오아파트 501동 1802호"],
        ["면    적", "전용면적 114.85 ㎡"],
        ["구    조", "철근콘크리트조 아파트"],
        ["등기사항", "근저당권 없음 (계약일 기준 등기부등본 확인 완료)"],
    ], [30*mm, RM-LM-30*mm], row_height=6.5*mm)

    y -= 2*mm
    c.setFont("KR-B", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["전세 보증금", "금 팔억원정  (₩ 800,000,000)"],
        ["계  약  금", "금 팔천만원정  (₩ 80,000,000)  — 계약 시 지급"],
        ["잔    금", "금 칠억이천만원정  (₩ 720,000,000)  — 2025년 12월 01일"],
        ["임대 기간", "2025년 12월 01일  ~  2027년 11월 30일  (24개월)"],
    ], [40*mm, RM-LM-40*mm], row_height=6.5*mm)

    y -= 4*mm
    y = section(c, y, "제1조 (목적)")
    y = body(c, y, "본 계약은 위 표시 부동산에 대한 임대차 계약을 체결함을 목적으로 한다.")

    y = section(c, y, "제2조 (임대차 기간)")
    y = body(c, y, "임대차 기간은 2025년 12월 1일부터 2027년 11월 30일까지 24개월로 한다.")

    y = section(c, y, "제3조 (임대인의 수선 의무)")
    y = body(c, y, "임대인은 임대차 기간 중 목적물의 사용·수익에 필요한 수선을 할 의무를 진다.")
    y = body(c, y, "소모성 부품(전구, 필터 등 50만원 미만)은 임차인 부담, 나머지 수선은 임대인 부담으로 한다.")

    y = section(c, y, "제4조 (원상복구)")
    y = body(c, y, "임차인은 계약 종료 시 통상적인 사용에 의한 마모·손상을 제외하고 원상복구 의무를 진다.")

    y = section(c, y, "제5조 (임대인의 출입)")
    y = body(c, y, "임대인은 목적물 점검 시 48시간 전 서면으로 임차인에게 사전 통보하고 임차인 동의 후 방문한다.")

    y = section(c, y, "제6조 (계약 해지)")
    y = body(c, y, "임대인은 주택임대차보호법에 규정된 사유 외에는 임차인의 의사에 반하여 계약을 해지할 수 없다.")
    y = body(c, y, "임차인의 계약갱신요구권(1회, 2년)을 보장한다.")

    y = section(c, y, "제7조 (보증금 반환)")
    y = body(c, y, "임대인은 임대차 기간 종료 후 임차인 퇴거 당일 보증금 전액을 반환한다.")
    y = body(c, y, "반환 지체 시 지체 일수에 대해 연 12%의 지연이자를 지급한다.")

    y = section(c, y, "제8조 (대항력 및 우선변제권)")
    y = body(c, y, "임차인은 전입신고, 확정일자 신청, 임차권등기 신청을 자유롭게 할 수 있다.")
    y = body(c, y, "임대인은 계약 기간 중 해당 주택에 추가 담보권 설정을 임차인에게 사전 고지하여야 한다.")

    y = section(c, y, "제9조 (전세보증보험)")
    y = body(c, y, "임차인은 주택도시보증공사(HUG) 또는 SGI서울보증의 전세보증보험 가입 권리를 가지며,")
    y = body(c, y, "임대인은 보험 가입에 필요한 서류 제공에 협조하여야 한다.")

    y -= 3*mm
    c.setFont("KR-B", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【임차인 보호 특약】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    specials = [
        "1. 임대인은 계약 체결 시 등기부등본을 교부하였으며, 근저당 등 권리관계 없음을 확인한다.",
        "2. 임대인의 매도 시 임차인에게 6개월 전 서면으로 우선 통보하여야 한다.",
        "3. 임대인은 계약 종료 후 30일 이내 보증금 미반환 시 이행보증 책임을 진다.",
        "4. 관리비 중 임대인 귀책분(공용 시설 수선 등)은 임대인이 부담한다.",
        "5. 계약갱신요구권 행사 시 전세보증금 증액은 5% 이내로 제한한다.",
        "6. 임차인은 반려동물 사육(소형견 1마리)을 할 수 있다.",
    ]
    for s in specials:
        y = body(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년 11월   일  계약을 체결한다.")
    y -= 8*mm

    sign_block(c, y,
        landlord=["성  명: 강 준 호", "주  소: 서울시 서초구 반포동 500", "연락처: 010-4567-8901"],
        tenant= ["성  명: 윤 서 연", "주  소: 서울시 강동구 천호동 300", "연락처: 010-6543-2109"],
        agent_name="잠실파트너스공인중개사", agent_reg="05-라-01234",
    )
    footer(c)
    c.save()
    print(f"✅ {fname}")


# ── 실행 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    make_contract_01()
    make_contract_02()
    make_contract_03()
    make_contract_04()
    print()
    print("=" * 55)
    print("생성 완료 — 4개 계약서")
    print("=" * 55)
    print("  contract_01_jeonse_danger.pdf  전세 위험 (악성 집주인)")
    print("  contract_02_jeonse_normal.pdf  전세 표준 (약간 주의)")
    print("  contract_03_monthly_medium.pdf 월세 중간 위험")
    print("  contract_04_jeonse_safe.pdf    전세 우량 (임차인 보호)")
    print()
    print("예상 분석 결과:")
    print("  계약서 1: riskScore 85~95  (high/medium 다수)")
    print("  계약서 2: riskScore 35~50  (caution 위주)")
    print("  계약서 3: riskScore 55~70  (medium 혼재)")
    print("  계약서 4: riskScore 10~25  (safe 위주)")
