"""
계약똑똑 추가 테스트용 임대차 계약서 4종 생성기

09. contract_09_villa_gaptrade.pdf       신축 빌라 전세 — 깡통전세/갭투자 패턴 (🚨 위험)
10. contract_10_gosiwon_danger.pdf       고시원·원룸 — 열악한 주거환경 + 인권침해 조항 (🚨 위험)
11. contract_11_house_monthly_caution.pdf  단독주택 월세 — 관리비 불투명 + 수선비 이슈 (⚠️ 주의)
12. contract_12_redevelop_jeonse_safe.pdf  재개발 예정지 전세 — 이주비·입주권 특약 완비 (⚠️ 주의~✅ 정상)

실행: python make_contracts_09_12.py
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
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
    sys.exit("한글 폰트 없음")
pdfmetrics.registerFont(TTFont("KR",  font_path))
pdfmetrics.registerFont(TTFont("KRB", font_path))

W, H = A4
LM = 18 * mm
RM = W - 18 * mm
TM = H - 18 * mm
BM = 22 * mm
LINE_H = 6.5 * mm
SEC_H  = 7.5 * mm
GAP    = 3   * mm


def title_block(c, subtitle, label):
    c.setFillColorRGB(0.08, 0.35, 0.72)
    c.rect(LM, TM - 22*mm, RM - LM, 20*mm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("KRB", 15)
    c.drawCentredString(W/2, TM - 10*mm, subtitle)
    c.setFont("KR", 9)
    c.drawCentredString(W/2, TM - 16*mm, label)
    c.setFillColorRGB(0, 0, 0)
    return TM - 26*mm


def draw_table(c, y, rows, col_widths, rh=6.5*mm):
    for ri, row in enumerate(rows):
        x = LM
        for ci, (cell, cw) in enumerate(zip(row, col_widths)):
            if ri == 0:
                c.setFillColorRGB(0.88, 0.92, 0.98)
            elif ci == 0:
                c.setFillColorRGB(0.95, 0.95, 0.95)
            else:
                c.setFillColorRGB(1, 1, 1)
            c.rect(x, y - rh, cw, rh, fill=1, stroke=1)
            c.setFillColorRGB(0, 0, 0)
            c.setFont("KRB" if ri == 0 else "KR", 8.5 if ri == 0 else 9)
            c.drawString(x + 2.5*mm, y - rh + 2.8*mm, str(cell))
            x += cw
        y -= rh
    return y - 2*mm


def sec(c, y, text):
    y -= GAP
    if y < BM + 15*mm:
        c.showPage(); y = TM - 5*mm
    c.setFont("KRB", 10)
    c.setFillColorRGB(0.08, 0.35, 0.72)
    c.drawString(LM, y, text)
    c.setFillColorRGB(0, 0, 0)
    return y - SEC_H


def bod(c, y, text, indent=0):
    if y < BM + 12*mm:
        c.showPage(); y = TM - 5*mm
    c.setFont("KR", 9)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    c.drawString(LM + indent*mm, y, text)
    return y - LINE_H


def sign_block(c, y, landlord, tenant, agent="(주)신뢰공인중개사", reg="11-가-99999"):
    if y < BM + 60*mm:
        c.showPage(); y = TM - 5*mm
    c.setStrokeColorRGB(0.5, 0.5, 0.5)
    c.line(LM, y, RM, y); y -= 6*mm
    c.setFont("KRB", 9.5); c.setFillColorRGB(0.08, 0.35, 0.72)
    c.drawString(LM, y, "【계약당사자 확인 및 서명】")
    c.setFillColorRGB(0, 0, 0); y -= 9*mm
    col = (RM - LM) / 2; rg = 6.5*mm
    for i, (lbl, info) in enumerate([("임 대 인", landlord), ("임 차 인", tenant)]):
        cx = LM + i * col; ty = y
        c.setFont("KRB", 9); c.drawString(cx, ty, lbl); ty -= rg
        c.setFont("KR", 8.5)
        for line in info:
            c.drawString(cx + 2*mm, ty, line); ty -= rg
        c.setStrokeColorRGB(0.8, 0.1, 0.1); c.setLineWidth(1.5)
        c.circle(cx + col - 14*mm, y - rg, 7*mm, stroke=1, fill=0)
        c.setFont("KR", 5.5); c.setFillColorRGB(0.8, 0.1, 0.1)
        c.drawCentredString(cx + col - 14*mm, y - rg - 1.5*mm, "인")
        c.setFillColorRGB(0, 0, 0); c.setLineWidth(0.5)
    y -= (len(landlord) + 2) * rg
    y -= 4*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "개업공인중개사"); y -= rg
    c.setFont("KR", 8.5)
    for line in [f"상호: {agent}", f"등록번호: {reg}", "소재지: 서울시 서초구 서초대로 10"]:
        c.drawString(LM + 2*mm, y, line); y -= rg
    return y


def footer(c):
    c.setFont("KR", 7); c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(W/2, BM - 5*mm, "본 계약서는 계약똑똑 AI 분석 테스트용 샘플입니다.")
    c.setFillColorRGB(0, 0, 0)


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 09: 신축 빌라 전세 — 깡통전세·갭투자 패턴
# 예상: 🚨 위험  (고위험 6개: 선순위담보 고지거부·추가담보허용·보험불가 등)
# ══════════════════════════════════════════════════════════════════════════════
def make_09():
    fname = "contract_09_villa_gaptrade.pdf"
    c = canvas.Canvas(fname, pagesize=A4)
    y = title_block(c, "주택 전세 임대차 계약서", "【위험 — 신축 빌라 깡통전세·갭투자 의심 조항 포함】")

    y -= 3*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "경기도 화성시 반월동 22-3, 반월신축빌라 신관 402호"],
        ["면    적", "전용면적 68.42 ㎡  (다세대주택)"],
        ["준공연도", "2025년 3월 준공 (신축)"],
        ["등기사항", "근저당권 2억 5,000만원 (㈜대박상호저축은행)  ← 주의"],
    ], [30*mm, RM-LM-30*mm])

    y -= 2*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["전세 보증금", "금 이억사천만원정  (₩ 240,000,000)"],
        ["계  약  금", "금 이천사백만원정  (₩ 24,000,000) — 계약 당일 지급"],
        ["잔    금", "금 이억일천육백만원정  (₩ 216,000,000) — 2025년 09월 30일"],
        ["임대 기간", "2025년 10월 01일  ~  2027년 09월 30일  (24개월)"],
        ["매매 호가", "※ 동일 평형 매매가 약 2억 5,000만원 (시세 대비 96% 전세)"],
    ], [40*mm, RM-LM-40*mm])

    y -= 4*mm
    y = sec(c, y, "제1조 (목적)")
    y = bod(c, y, "본 계약은 위 표시 부동산에 대한 전세 임대차 계약을 목적으로 한다.")

    y = sec(c, y, "제2조 (선순위 담보 고지 거부)")   # ← 고위험
    y = bod(c, y, "① 임대인은 본 주택에 설정된 근저당권 내역을 임차인에게 별도 고지하지 않는다.")
    y = bod(c, y, "② 임차인은 등기부를 독자적으로 확인하여 계약하며, 담보 관련 이의를 포기한다.")

    y = sec(c, y, "제3조 (추가 담보 설정 허용)")   # ← 고위험
    y = bod(c, y, "임대인은 계약 기간 중 본 주택에 추가 담보대출을 자유롭게 실행할 수 있으며,")
    y = bod(c, y, "임차인은 이로 인한 후순위 전락에 대해 어떠한 이의도 제기할 수 없다.")

    y = sec(c, y, "제4조 (전세보증보험 가입 불가 동의)")   # ← 고위험
    y = bod(c, y, "① 본 주택은 전세보증보험(HUG·SGI) 가입 기준을 충족하지 못할 수 있다.")
    y = bod(c, y, "② 임차인은 보험 가입 불가 사실을 인지하였으며 이를 이유로 계약을 파기할 수 없다.")

    y = sec(c, y, "제5조 (매도·경매 시 우선 정산 배제)")   # ← 고위험
    y = bod(c, y, "임대인이 본 주택을 매도하거나 경매가 진행될 경우,")
    y = bod(c, y, "임차인은 선순위 근저당권자에 대해 우선 정산을 주장할 수 없다.")

    y = sec(c, y, "제6조 (임차권등기명령 신청 금지)")   # ← 고위험
    y = bod(c, y, "임차인은 계약 기간 중 및 종료 후에도 임차권등기명령 신청을 하지 않기로 합의한다.")

    y = sec(c, y, "제7조 (보증금 반환 조건)")
    y = bod(c, y, "임대인은 신규 임차인을 직접 구하여 보증금을 이전하는 방식으로 반환할 수 있으며,")
    y = bod(c, y, "신규 임차인 미확보 시 보증금 반환 시기는 확정되지 않는다.")  # ← 중위험

    y -= 3*mm
    c.setFont("KRB", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【특약사항】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    for s in [
        "1. 본 계약은 임대인이 신축 직후 임대하는 것으로, 매매가와 전세가의 차액이 없음을 확인한다.",  # 고위험
        "2. 전세 기간 중 임대인의 세금 체납으로 인한 공매 처분 시 임차인은 이에 동의한다.",  # 고위험
        "3. 임차인은 계약 체결 전 법무사 검토 없이 서명하였음을 확인한다.",
        "4. 분양대행사 소개로 이루어진 본 계약의 중개보수는 임차인이 전액 부담한다.",
    ]:
        y = bod(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년 9월 15일 계약을 체결한다.")
    y -= 8*mm
    sign_block(c, y,
        landlord=["성  명: 갭 투 기", "주  소: 서울시 강남구 역삼동 1", "연락처: 010-6666-7777"],
        tenant= ["성  명: 임 피 해", "주  소: 경기도 수원시 팔달구 우만동 2", "연락처: 010-3333-4444"],
        agent="반월부동산중개", reg="13-마-00321",
    )
    footer(c); c.save(); print(f"✅ {fname}")


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 10: 고시원·원룸 — 열악한 주거환경 + 인권침해성 조항
# 예상: 🚨 위험  (불법 자력구제 + 전입신고 금지 + 과도한 통제)
# ══════════════════════════════════════════════════════════════════════════════
def make_10():
    fname = "contract_10_gosiwon_danger.pdf"
    c = canvas.Canvas(fname, pagesize=A4)
    y = title_block(c, "원룸 임대차 계약서", "【위험 — 과도한 통제 및 인권침해성 조항 포함】")

    y -= 3*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "서울특별시 관악구 봉천동 77-1, 봉천원룸텔 3층 305호"],
        ["면    적", "전용면적 9.9 ㎡ (고시원형 원룸)"],
        ["구    조", "철근콘크리트조 다중주택"],
    ], [30*mm, RM-LM-30*mm])

    y -= 2*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["보  증  금", "금 오백만원정  (₩ 5,000,000)"],
        ["월    세", "금 삼십오만원정  (₩ 350,000) — 매월 1일 선불"],
        ["임대 기간", "2025년 08월 01일  ~  2026년 07월 31일  (12개월)"],
        ["관  리  비", "월 70,000원 (공용전기·수도·와이파이 포함)"],
    ], [40*mm, RM-LM-40*mm])

    y -= 4*mm
    y = sec(c, y, "제1조 (목적)")
    y = bod(c, y, "본 계약은 위 표시 원룸에 대한 임대차 계약을 목적으로 한다.")

    y = sec(c, y, "제2조 (출입 및 방문객 통제)")   # ← 고위험 (인권침해)
    y = bod(c, y, "① 임대인은 보안 목적으로 임차인의 귀가 시간(23:00~06:00)을 제한할 수 있다.")
    y = bod(c, y, "② 임차인은 관리인실 등록 없이 방문객을 건물 내부로 데려올 수 없다.")
    y = bod(c, y, "③ 이성 방문객의 숙박을 금지하며 위반 시 임대인은 즉시 계약을 해지할 수 있다.")

    y = sec(c, y, "제3조 (불법 자력 구제)")   # ← 고위험
    y = bod(c, y, "① 임차인이 차임을 1일이라도 연체하면 임대인은 즉시 열쇠를 교체할 수 있다.")
    y = bod(c, y, "② 임차인의 짐은 임대인이 임의로 처분할 수 있으며 임차인은 이에 이의를 포기한다.")

    y = sec(c, y, "제4조 (전입신고 금지)")   # ← 고위험
    y = bod(c, y, "임차인은 본 주소지에 주민등록 전입신고를 하지 않기로 확약하며,")
    y = bod(c, y, "위반 시 임대인은 즉시 계약을 해지하고 보증금에서 손해액을 공제한다.")

    y = sec(c, y, "제5조 (공용시설 이용 제한)")   # ← 중위험
    y = bod(c, y, "① 공용 주방 이용 시간은 07:00~22:00으로 제한한다.")
    y = bod(c, y, "② 세탁기는 1일 1회, 1회 30분 이내로 이용을 제한한다.")
    y = bod(c, y, "③ 공용시설 청소를 임차인이 순번에 따라 의무 수행한다.")

    y = sec(c, y, "제6조 (개인물품 보관 제한)")   # ← 중위험
    y = bod(c, y, "임차인은 복도·공용공간에 개인 물품을 보관할 수 없으며,")
    y = bod(c, y, "위반 물품은 임대인이 즉시 폐기할 수 있다.")

    y = sec(c, y, "제7조 (원상복구)")
    y = bod(c, y, "임차인은 입주 당시 상태로 원상복구하여야 하며,")
    y = bod(c, y, "도배·장판 교체 비용도 임차인이 전액 부담한다.")  # ← 중위험

    y = sec(c, y, "제8조 (보증금 반환)")
    y = bod(c, y, "임대인은 임차인 퇴거 후 60일 이내에 보증금을 반환한다.")  # ← 중위험(60일은 과도)
    y = bod(c, y, "관리비 미납·원상복구 비용·연체이자 등 전액 공제 후 잔액을 반환한다.")

    y -= 3*mm
    c.setFont("KRB", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【특약사항】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    for s in [
        "1. 임차인은 확정일자 신청 및 임차권등기명령 신청을 하지 않기로 동의한다.",  # 고위험
        "2. 관리비에 포함되지 않은 개별 전기 사용료는 임차인이 직접 부담한다.",
        "3. 소음·분쟁 발생 시 임대인은 1회 경고 후 즉시 퇴거를 요구할 수 있다.",
        "4. 음식물 냄새·흡연 등으로 인한 도배 오염은 임차인이 전액 부담한다.",
    ]:
        y = bod(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년 7월 28일 계약을 체결한다.")
    y -= 8*mm
    sign_block(c, y,
        landlord=["성  명: 권 통 제", "주  소: 서울시 관악구 신림동 50", "연락처: 010-2222-3333"],
        tenant= ["성  명: 하 을 수", "주  소: 서울시 도봉구 창동 10", "연락처: 010-4444-5555"],
        agent="봉천공인중개사사무소", reg="21-바-00654",
    )
    footer(c); c.save(); print(f"✅ {fname}")


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 11: 단독주택 월세 — 관리비 불투명 + 수선비 이슈 (주의 수준)
# 예상: ⚠️ 주의  (medium 3개 — 관리비 미공개, 수선비 분담 불명확, 12시간 통보)
# ══════════════════════════════════════════════════════════════════════════════
def make_11():
    fname = "contract_11_house_monthly_caution.pdf"
    c = canvas.Canvas(fname, pagesize=A4)
    y = title_block(c, "주택 월세 임대차 계약서", "【주의 — 관리비·수선비 분담 불명확 조항 포함】")

    y -= 3*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "경기도 용인시 처인구 김량장동 33-7, 단독주택 2층"],
        ["면    적", "전용면적 66.12 ㎡  (단독주택 2층)"],
        ["구    조", "조적조 단독주택 (1978년 준공)"],
        ["등기사항", "소유권 이전 완료, 근저당 없음"],
    ], [30*mm, RM-LM-30*mm])

    y -= 2*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["보  증  금", "금 일천오백만원정  (₩ 15,000,000)"],
        ["월    세", "금 오십오만원정  (₩ 550,000) — 매월 5일 선불"],
        ["임대 기간", "2025년 09월 01일  ~  2026년 08월 31일  (12개월)"],
        ["관  리  비", "월 100,000원 (항목 미공개 정액제)"],   # ← 중위험
    ], [40*mm, RM-LM-40*mm])

    y -= 4*mm
    y = sec(c, y, "제1조 (목적)")
    y = bod(c, y, "본 계약은 단독주택 2층에 대한 월세 임대차 계약을 목적으로 한다.")

    y = sec(c, y, "제2조 (임대차 기간)")
    y = bod(c, y, "임대차 기간은 2025년 9월 1일부터 2026년 8월 31일까지 12개월로 한다.")

    y = sec(c, y, "제3조 (관리비)")   # ← 중위험 (항목 불투명)
    y = bod(c, y, "① 관리비는 월 100,000원 정액으로 납부한다.")
    y = bod(c, y, "② 관리비 항목 세부 내역은 임대인이 필요에 따라 변경할 수 있으며 임차인은 이에 따른다.")
    y = bod(c, y, "③ 냉·난방비, 주차비는 관리비와 별도로 임차인이 실비 정산한다.")

    y = sec(c, y, "제4조 (수선 의무)")   # ← 중위험 (분담 불명확)
    y = bod(c, y, "① 소모성 부품(전구·배터리·배수구 필터 등) 교체는 임차인이 부담한다.")
    y = bod(c, y, "② 노후화·자연마모에 의한 수선 범위 및 비용 분담은 임대인·임차인이 별도 협의한다.")
    y = bod(c, y, "③ 긴급 수선 시 임차인이 선 수리 후 임대인에게 청구할 수 있으나,")
    y = bod(c, y, "   임대인의 사전 승인 없이 지출된 비용은 임대인이 환급을 거부할 수 있다.")  # ← 중위험

    y = sec(c, y, "제5조 (임대인 출입)")
    y = bod(c, y, "임대인은 점검 목적으로 12시간 전 구두 통보 후 방문할 수 있다.")  # ← 주의(12시간은 짧음)

    y = sec(c, y, "제6조 (원상복구)")
    y = bod(c, y, "임차인은 계약 종료 시 목적물을 입주 당시 상태로 원상복구하여야 한다.")
    y = bod(c, y, "자연 노후화 항목의 원상복구 여부는 임대인·임차인이 협의로 결정한다.")

    y = sec(c, y, "제7조 (보증금 반환)")
    y = bod(c, y, "임대인은 임차인 퇴거 확인 후 14일 이내에 보증금을 반환한다.")
    y = bod(c, y, "단, 관리비·수선비 정산 완료 후 잔액을 반환한다.")

    y = sec(c, y, "제8조 (대항력)")
    y = bod(c, y, "임차인은 전입신고 및 확정일자를 자유롭게 신청할 수 있다.")

    y -= 3*mm
    c.setFont("KRB", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【특약사항】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    for s in [
        "1. 건물 준공 후 40년 이상 경과한 노후 주택으로, 입주 전 하자 내역을 현황대로 임대한다.",
        "2. 보일러 고장 시 임대인이 수리하되, 수리 지연으로 인한 손해는 임차인이 부담한다.",  # 주의
        "3. 1층 임대인 거주 공간과 2층 임차인 공간은 공유 계단을 사용하며 분쟁은 협의로 해결한다.",
        "4. 주차 공간 1대 제공, 임대인 방문 시 임시 사용 가능하다.",
        "5. 화재보험은 임차인이 독자적으로 가입한다.",
    ]:
        y = bod(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년 8월 20일 계약을 체결한다.")
    y -= 8*mm
    sign_block(c, y,
        landlord=["성  명: 노 구 건", "주  소: 경기도 용인시 처인구 김량장동 33-7 1층", "연락처: 010-7777-8888"],
        tenant= ["성  명: 오 적 당", "주  소: 경기도 성남시 분당구 야탑동 100", "연락처: 010-8888-7777"],
        agent="용인처인중개사", reg="17-사-00987",
    )
    footer(c); c.save(); print(f"✅ {fname}")


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 12: 재개발 예정지 전세 — 이주비·입주권 특약 완비
# 예상: ⚠️ 주의~✅ 정상  (재개발 특성상 주의이나 임차인 보호 특약 완비)
# ══════════════════════════════════════════════════════════════════════════════
def make_12():
    fname = "contract_12_redevelop_jeonse_safe.pdf"
    c = canvas.Canvas(fname, pagesize=A4)
    y = title_block(c, "주택 전세 임대차 계약서", "【주의~정상 — 재개발구역, 이주비·입주권 특약 완비】")

    y -= 3*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "서울특별시 동대문구 전농동 55-12, 전농1구역 재개발 대상 주택 2층"],
        ["면    적", "전용면적 49.58 ㎡  (다세대주택)"],
        ["구역 현황", "정비구역 지정 완료, 사업시행인가 준비 중 (2027년 이주 예정)"],
        ["등기사항", "근저당 없음 (등기부등본 교부 완료)"],
    ], [30*mm, RM-LM-30*mm])

    y -= 2*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["전세 보증금", "금 일억이천만원정  (₩ 120,000,000)"],
        ["계  약  금", "금 일천이백만원정  (₩ 12,000,000) — 계약 시 지급"],
        ["잔    금", "금 일억팔백만원정  (₩ 108,000,000) — 2025년 10월 01일"],
        ["임대 기간", "2025년 10월 01일  ~  2027년 09월 30일  (24개월)"],
    ], [40*mm, RM-LM-40*mm])

    y -= 4*mm
    y = sec(c, y, "제1조 (목적)")
    y = bod(c, y, "본 계약은 위 표시 부동산에 대한 전세 임대차 계약을 목적으로 한다.")

    y = sec(c, y, "제2조 (재개발 구역 고지)")   # ← 주의이나 고지 완료 → 긍정
    y = bod(c, y, "① 임대인은 본 주택이 서울시 전농1구역 재개발정비구역 내에 위치함을 사전 고지하였다.")
    y = bod(c, y, "② 사업시행인가 이후 이주 시기가 확정될 수 있으며, 임차인은 이를 인지하고 동의하였다.")

    y = sec(c, y, "제3조 (임대차 기간 보장)")
    y = bod(c, y, "임대인은 임차인에게 최소 24개월의 임대차 기간을 보장하며,")
    y = bod(c, y, "재개발 이주가 이보다 일찍 결정되는 경우 제4조의 이주보상 조항을 적용한다.")

    y = sec(c, y, "제4조 (조기 이주 시 보상)")   # ← 임차인 보호
    y = bod(c, y, "① 사업시행인가에 따라 임차인이 기간 만료 전 이주해야 하는 경우,")
    y = bod(c, y, "   임대인은 잔여 기간 월세 상당액 + 이사비 300만원을 임차인에게 지급한다.")
    y = bod(c, y, "② 조기 이주 통보는 최소 6개월 전 서면으로 이루어져야 한다.")

    y = sec(c, y, "제5조 (보증금 반환)")
    y = bod(c, y, "① 임대인은 계약 종료 또는 조기 이주 시 임차인 퇴거 당일 보증금 전액을 반환한다.")
    y = bod(c, y, "② 반환 지체 시 연 12%의 지연이자를 가산하여 지급한다.")

    y = sec(c, y, "제6조 (대항력 및 우선변제권)")
    y = bod(c, y, "임차인은 전입신고, 확정일자, 임차권등기 신청을 자유롭게 할 수 있다.")
    y = bod(c, y, "임대인은 보증금 반환 보증보험 가입에 필요한 서류를 즉시 제공하여야 한다.")

    y = sec(c, y, "제7조 (수선 의무)")
    y = bod(c, y, "임대인은 주요 설비(보일러·상하수도·전기설비)의 수선 의무를 지며 비용을 부담한다.")
    y = bod(c, y, "소모성 부품(50만원 미만)은 임차인 부담으로 하며 영수증 제출 시 50%를 임대인이 환급한다.")

    y -= 3*mm
    c.setFont("KRB", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【임차인 보호 특약】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    for s in [
        "1. 임대인은 계약 체결 시 토지·건물 등기부등본, 재개발 구역 지정 고시문을 교부하였음을 확인한다.",
        "2. 재개발 조합 설립 인가 이후 임차인에게 세입자 권리 정보(이주대책·이주비 지원 등)를 안내한다.",
        "3. 임차인의 계약갱신요구권 행사는 이주 확정 통보가 없는 한 임대인이 거절할 수 없다.",
        "4. 임대인은 계약 기간 중 해당 주택에 추가 담보권을 설정하지 않기로 한다.",
        "5. 전세보증보험(HUG) 가입 요건을 충족하며 임대인은 필요 서류를 즉시 제공한다.",
        "6. 이주비 지원이 확정될 경우 임차인은 공공 이주비 우선 신청권을 가진다.",
    ]:
        y = bod(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년 9월 20일 계약을 체결한다.")
    y -= 8*mm
    sign_block(c, y,
        landlord=["성  명: 전 재 개", "주  소: 서울시 동대문구 전농동 55-12 1층", "연락처: 010-1234-9876"],
        tenant= ["성  명: 나 안 심", "주  소: 서울시 성북구 길음동 200", "연락처: 010-9876-1234"],
        agent="전농공인중개사사무소", reg="02-아-00543",
    )
    footer(c); c.save(); print(f"✅ {fname}")


# ── 실행 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    make_09()
    make_10()
    make_11()
    make_12()
    print()
    print("=" * 65)
    print("추가 테스트 계약서 4종 생성 완료  (09~12번)")
    print("=" * 65)
    print("  09: 신축 빌라 전세  — 깡통전세·갭투자 의심 패턴")
    print("  10: 원룸·고시원    — 불법 자력구제 + 전입신고 금지 + 과도한 통제")
    print("  11: 단독주택 월세  — 관리비 불투명 + 수선비 분담 불명확")
    print("  12: 재개발 예정지  — 조기이주 보상·대항력 특약 완비 (주의~정상)")
    print()
    print("예상 분석 결과:")
    print("  09 → 🚨 위험  (깡통전세 고위험 6개: 담보고지거부·추가담보허용·보험불가 등)")
    print("  10 → 🚨 위험  (불법 자력구제·전입신고 금지·인권침해성 통제 조항)")
    print("  11 → ⚠️ 주의  (medium 3개: 관리비 불투명·긴급수선 사전승인·12시간 통보)")
    print("  12 → ⚠️ 주의  (재개발 특성 주의 + 임차인 보호 완비로 경계 수준)")
