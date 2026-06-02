"""
계약똑똑 추가 테스트용 임대차 계약서 4종 생성기

5. contract_05_monthly_danger.pdf     월세 — 악성 임대인 (차임 인상, 단전단수, 갱신요구권 포기)
6. contract_06_officetel_caution.pdf  오피스텔 — 전입신고 금지 세무 회피형
7. contract_07_jeonse_sagi_danger.pdf 전세사기 의심 — 신탁 미동의 + 대항력 무력화
8. contract_08_monthly_safe.pdf       월세 — 착한 임대인 (수선 의무, 중도해지 위약금 없음)
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
        # 도장
        c.setStrokeColorRGB(0.8, 0.1, 0.1); c.setLineWidth(1.5)
        c.circle(cx + col - 14*mm, y - rg, 7*mm, stroke=1, fill=0)
        c.setFont("KR", 5.5); c.setFillColorRGB(0.8, 0.1, 0.1)
        c.drawCentredString(cx + col - 14*mm, y - rg - 1.5*mm, "인")
        c.setFillColorRGB(0, 0, 0); c.setLineWidth(0.5)
    y -= (len(landlord) + 2) * rg
    y -= 4*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "개업공인중개사"); y -= rg
    c.setFont("KR", 8.5)
    for line in [f"상호: {agent}", f"등록번호: {reg}", "소재지: 서울시 강남구 테헤란로 1"]:
        c.drawString(LM + 2*mm, y, line); y -= rg
    return y


def footer(c):
    c.setFont("KR", 7); c.setFillColorRGB(0.5, 0.5, 0.5)
    c.drawCentredString(W/2, BM - 5*mm, "본 계약서는 계약똑똑 AI 분석 테스트용 샘플입니다.")
    c.setFillColorRGB(0, 0, 0)


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 5: 월세 — 악성 임대인
# 예상: 🚨 위험   (high 2 + medium 3 → 단연 Red)
# ══════════════════════════════════════════════════════════════════════════════
def make_05():
    fname = "contract_05_monthly_danger.pdf"
    c = canvas.Canvas(fname, pagesize=A4)
    y = title_block(c, "주택 월세 임대차 계약서", "【위험 — 차임 일방 인상 및 강제 퇴거 조항 포함】")

    y -= 3*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "서울특별시 마포구 염리동 444, 염리빌라 201호"],
        ["면    적", "전용면적 45.12 ㎡  (다세대주택)"],
        ["구    조", "철근콘크리트조 다세대"],
    ], [30*mm, RM-LM-30*mm])

    y -= 2*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["보  증  금", "금 삼천만원정  (₩ 30,000,000)"],
        ["월    세", "금 일백오십만원정  (₩ 1,500,000) — 매월 25일 선불"],
        ["임대 기간", "2025년 08월 01일  ~  2026년 07월 31일  (12개월)"],
    ], [40*mm, RM-LM-40*mm])

    y -= 4*mm
    y = sec(c, y, "제1조 (목적)")
    y = bod(c, y, "본 계약은 위 표시 부동산에 대한 월세 임대차 계약을 목적으로 한다.")

    y = sec(c, y, "제2조 (임대차 기간)")
    y = bod(c, y, "임대차 기간은 2025년 8월 1일부터 2026년 7월 31일까지 12개월로 한다.")

    y = sec(c, y, "제3조 (차임 일방 인상)")   # ← 고위험 (임차인보호법 5% 상한 위반)
    y = bod(c, y, "① 임대인은 물가상승·세금 부담 증가 등을 이유로 매년 차임을 최대 15% 일방 인상할 수 있다.")
    y = bod(c, y, "② 임차인은 인상 통보 후 5일 이내에 서면으로 수락하지 않으면 계약 해지로 간주한다.")

    y = sec(c, y, "제4조 (연체 즉시 자력 구제)")   # ← 고위험 (불법 자력 구제)
    y = bod(c, y, "① 임차인이 차임을 약정 기일로부터 1일이라도 연체하면 임대인은 즉시 계약을 해지할 수 있다.")
    y = bod(c, y, "② 임대인은 연체 즉시 단전·단수·잠금장치 교체 등의 조치를 취할 수 있으며,")
    y = bod(c, y, "   임차인은 이에 대해 형사·민사상 일체의 이의를 제기하지 않기로 한다.")

    y = sec(c, y, "제5조 (수선 책임 임차인 전가)")   # ← 중위험
    y = bod(c, y, "보일러·싱크대·배관 등 모든 설비의 파손 수리 비용은 원인 불문하고 임차인이 전액 부담한다.")

    y = sec(c, y, "제6조 (중도해지 위약금)")   # ← 중위험
    y = bod(c, y, "임차인이 중도 퇴거 시 잔여 기간에 관계없이 보증금의 20%를 위약금으로 임대인에게 귀속한다.")

    y -= 3*mm
    c.setFont("KRB", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【특약사항】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    for s in [
        "1. 임차인은 주택임대차보호법상 계약갱신요구권을 일체 행사하지 않기로 사전 포기한다.",  # 고위험
        "2. 연체 차임에 대해 연 20% 지연이자를 가산하며, 보증금에서 즉시 공제한다.",  # 중위험
        "3. 임차인은 임대인 동의 없이 방문객을 숙박시킬 수 없으며 위반 시 당일 퇴거한다.",
    ]:
        y = bod(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년 7월 15일 계약을 체결한다.")
    y -= 8*mm
    sign_block(c, y,
        landlord=["성  명: 최 독 점", "주  소: 서울시 강남구 압구정로 11", "연락처: 010-8888-9999"],
        tenant= ["성  명: 안 을 기", "주  소: 서울시 은평구 녹번동 22", "연락처: 010-7777-6666"],
    )
    footer(c); c.save(); print(f"✅ {fname}")


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 6: 오피스텔 — 전입신고 금지 (세무 회피형)
# 예상: 🚨 위험  (전입신고 금지는 고위험 + 세무손해 전가 특약)
# ══════════════════════════════════════════════════════════════════════════════
def make_06():
    fname = "contract_06_officetel_caution.pdf"
    c = canvas.Canvas(fname, pagesize=A4)
    y = title_block(c, "주거용 오피스텔 임대차 계약서", "【위험 — 전입신고 금지 및 조세 손해 임차인 전가 포함】")

    y -= 3*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "서울특별시 영등포구 여의도동 55-6, 여의도드림오피스텔 808호"],
        ["면    적", "전용면적 29.85 ㎡"],
        ["구    조", "철골조 오피스텔"],
    ], [30*mm, RM-LM-30*mm])

    y -= 2*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["보  증  금", "금 일천만원정  (₩ 10,000,000)"],
        ["월    세", "금 팔십만원정  (₩ 800,000) — 매월 1일 선불 지급"],
        ["임대 기간", "2025년 09월 01일  ~  2026년 08월 31일  (12개월)"],
        ["관  리  비", "정액 200,000원 (전기·수도 별도)"],
    ], [40*mm, RM-LM-40*mm])

    y -= 4*mm
    y = sec(c, y, "제1조 (목적)")
    y = bod(c, y, "본 계약은 오피스텔에 대한 임대차 계약을 목적으로 한다.")

    y = sec(c, y, "제2조 (용도 제한)")   # ← 주의
    y = bod(c, y, "임차인은 본 오피스텔을 업무용으로만 사용하여야 하며, 주거용 시설 추가를 금지한다.")

    y = sec(c, y, "제3조 (전입신고 금지)")   # ← 고위험 (대항력 취득 원천 차단)
    y = bod(c, y, "① 임차인은 본 오피스텔 주소지에 주민등록 전입신고를 절대 하지 않기로 확약한다.")
    y = bod(c, y, "② 임차인이 무단으로 전입신고를 한 경우 임대인은 즉시 계약을 해지할 수 있다.")

    y = sec(c, y, "제4조 (조세 손해 배상)")   # ← 고위험 (세무 손해 임차인 전가)
    y = bod(c, y, "임차인의 전입신고로 인해 임대인에게 부가세 환급 반환·종합소득세 부담 등")
    y = bod(c, y, "조세 불이익이 발생할 경우, 그 손실 전액을 임차인이 배상하고 즉시 퇴거한다.")

    y = sec(c, y, "제5조 (반려동물 및 흡연 금지)")   # ← 주의
    y = bod(c, y, "① 반려동물 사육을 금지하며 위반 시 청소비 100만원 및 즉시 계약 해지가 적용된다.")
    y = bod(c, y, "② 실내외 흡연을 금지한다.")

    y -= 3*mm
    c.setFont("KRB", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【특약사항】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    for s in [
        "1. 본 건은 임대인의 세무상 지위 유지를 위해 업무용으로 등록되며 임차인은 이에 동의한다.",
        "2. 임차인은 확정일자 신청 및 임차권등기명령 신청을 하지 않기로 동의한다.",  # 고위험
        "3. 임차인은 임대차보호법상 보증금 반환 보증보험 가입 권리를 포기한다.",  # 고위험
    ]:
        y = bod(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년 8월 20일 계약을 체결한다.")
    y -= 8*mm
    sign_block(c, y,
        landlord=["성  명: 박 세 무", "주  소: 서울시 서초구 서초대로 3", "연락처: 010-3333-2222"],
        tenant= ["성  명: 이 몰 라", "주  소: 서울시 마포구 창전동 8", "연락처: 010-1111-2222"],
    )
    footer(c); c.save(); print(f"✅ {fname}")


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 7: 전세 — 전세사기 의심 (신탁 미동의 + 대항력 무력화)
# 예상: 🚨 위험  (고위험 5개 이상, 실제 전세사기 패턴)
# ══════════════════════════════════════════════════════════════════════════════
def make_07():
    fname = "contract_07_jeonse_sagi_danger.pdf"
    c = canvas.Canvas(fname, pagesize=A4)
    y = title_block(c, "주택 전세 임대차 계약서", "【위험 — 전세사기 의심 조항 다수 포함】")

    y -= 3*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "인천광역시 미추홀구 주안동 111-2, 주안드림파크 703호"],
        ["면    적", "전용면적 72.84 ㎡"],
        ["등기사항", "※ 한국자산신탁 신탁등기 설정 중 (임대인 직권 계약)"],
    ], [30*mm, RM-LM-30*mm])

    y -= 2*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["전세 보증금", "금 삼억원정  (₩ 300,000,000)"],
        ["계  약  금", "금 삼천만원정  (₩ 30,000,000)  — 계약 당일 즉시 지급"],
        ["잔    금", "금 이억칠천만원정  (₩ 270,000,000)  — 2025년 10월 30일"],
        ["임대 기간", "2025년 11월 01일  ~  2027년 10월 31일  (24개월)"],
    ], [40*mm, RM-LM-40*mm])

    y -= 4*mm
    y = sec(c, y, "제1조 (목적)")
    y = bod(c, y, "본 계약은 전세 임대차 계약 체결을 목적으로 한다.")

    y = sec(c, y, "제2조 (소유권 이전 및 바지 집주인)")   # ← 고위험
    y = bod(c, y, "① 임대인은 잔금 수령 후 즉시 제3자에게 소유권을 이전(매도)할 수 있다.")
    y = bod(c, y, "② 임차인은 소유권 이전에 대해 어떠한 이의도 제기하지 않으며 새 소유자의 요구에 따른다.")

    y = sec(c, y, "제3조 (근저당 추가 설정 허용)")   # ← 고위험
    y = bod(c, y, "① 임대인은 임차인의 전입신고일 당일 추가 근저당권을 설정할 수 있다.")
    y = bod(c, y, "② 해당 근저당은 임차인의 대항력보다 선순위로 간주하며 임차인은 이를 용인한다.")

    y = sec(c, y, "제4조 (신탁 동의서 미제출)")   # ← 고위험
    y = bod(c, y, "① 본 주택은 신탁회사에 신탁등기된 부동산으로, 임대는 신탁회사 동의 없이 체결된다.")
    y = bod(c, y, "② 임차인은 신탁 관련 법적 분쟁 발생 시 이를 임대인에게 책임 귀속시키지 않는다.")

    y = sec(c, y, "제5조 (선순위 채무 고지 거부)")   # ← 고위험
    y = bod(c, y, "임차인은 국세 체납·압류 여부·선순위 채무를 임대인에게 요구하지 않으며 전적으로 신뢰하기로 한다.")

    y -= 3*mm
    c.setFont("KRB", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【특약사항】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    for s in [
        "1. 임차인은 전세보증보험(HUG, SGI) 가입이 불가능하더라도 이를 이유로 계약을 해제할 수 없다.",  # 고위험
        "2. 경매·공매 발생 시 보증금 회수 불가에 대한 책임은 임차인에게 있다.",  # 고위험
        "3. 임차인은 대항력 취득 이전에 발생한 모든 권리 문제에 대해 이의 없이 수용한다.",  # 고위험
    ]:
        y = bod(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년 10월 10일 계약을 체결한다.")
    y -= 8*mm
    sign_block(c, y,
        landlord=["성  명: 바 지 킹", "주  소: 서울시 강서구 화곡동 33", "연락처: 010-4444-4444"],
        tenant= ["성  명: 손 해 자", "주  소: 인천시 부평구 부평동 99", "연락처: 010-9999-8888"],
    )
    footer(c); c.save(); print(f"✅ {fname}")


# ══════════════════════════════════════════════════════════════════════════════
# 계약서 8: 월세 — 착한 임대인 (임차인 보호 완비)
# 예상: ✅ 정상  (위험·주의 조항 없음)
# ══════════════════════════════════════════════════════════════════════════════
def make_08():
    fname = "contract_08_monthly_safe.pdf"
    c = canvas.Canvas(fname, pagesize=A4)
    y = title_block(c, "주택 월세 임대차 계약서", "【정상 — 임차인 보호 완비, 착한 임대인 계약】")

    y -= 3*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【부동산 표시】"); y -= 5*mm
    y = draw_table(c, y, [
        ["구분", "내용"],
        ["소 재 지", "서울특별시 노원구 상계동 111, 상계그린빌라 302호"],
        ["면    적", "전용면적 42.15 ㎡"],
        ["등기사항", "근저당 없음 (등기부등본 교부 완료)"],
    ], [30*mm, RM-LM-30*mm])

    y -= 2*mm
    c.setFont("KRB", 9); c.drawString(LM, y, "【계약 내용】"); y -= 5*mm
    y = draw_table(c, y, [
        ["항목", "금액"],
        ["보  증  금", "금 이천만원정  (₩ 20,000,000)"],
        ["월    세", "금 칠십만원정  (₩ 700,000) — 매월 10일 후불"],
        ["임대 기간", "2025년 08월 01일  ~  2026년 07월 31일  (12개월)"],
        ["관  리  비", "실사용량 기준 개별 청구 (불필요 정액제 없음)"],
    ], [40*mm, RM-LM-40*mm])

    y -= 4*mm
    y = sec(c, y, "제1조 (목적)")
    y = bod(c, y, "본 계약은 위 부동산에 대한 주거 월세 임대차 계약을 목적으로 한다.")

    y = sec(c, y, "제2조 (임대차 기간)")
    y = bod(c, y, "임대차 기간은 2025년 8월 1일부터 2026년 7월 31일까지 12개월로 한다.")

    y = sec(c, y, "제3조 (임대인의 수선 의무)")
    y = bod(c, y, "① 임대인은 보일러·수도·배관 등 주요 설비의 수선 의무를 지며 비용을 전액 부담한다.")
    y = bod(c, y, "② 10만원 미만의 소액 하자를 임차인이 수선한 경우 영수증 제출 시 즉시 환급한다.")

    y = sec(c, y, "제4조 (원상복구 면책)")
    y = bod(c, y, "임차인은 통상적 사용으로 인한 마모·벽지 변색·손상에 대해 원상복구 의무를 지지 않는다.")

    y = sec(c, y, "제5조 (중도해지 위약금 없음)")
    y = bod(c, y, "임차인은 이사·이직 등 부득이한 사정 시 1개월 전 서면 통보만으로 위약금 없이 해지 가능하다.")

    y = sec(c, y, "제6조 (보증금 반환)")
    y = bod(c, y, "임대인은 임차인 퇴거 당일 보증금 전액을 반환한다.")
    y = bod(c, y, "지체 시 지체 일수에 대해 연 12%의 지연이자를 지급한다.")

    y = sec(c, y, "제7조 (대항력 보장)")
    y = bod(c, y, "임차인은 전입신고·확정일자·임차권등기 신청을 자유롭게 할 수 있다.")

    y -= 3*mm
    c.setFont("KRB", 9); c.setFillColorRGB(0.08,0.35,0.72)
    c.drawString(LM, y, "【특약사항】"); c.setFillColorRGB(0,0,0); y -= 5*mm
    for s in [
        "1. 소형 반려동물 1마리(5kg 이하) 사육을 허용한다.",
        "2. 임대인은 계약일 기준 국세·지방세 완납 확인서를 교부하였다.",
        "3. 전세보증보험 가입 요건을 갖추며 필요 서류를 즉시 제공한다.",
        "4. 임차인의 계약갱신요구권 행사 시 임대인은 정당한 사유 없이 거절할 수 없다.",
    ]:
        y = bod(c, y, s, indent=2)

    y -= 5*mm
    c.setFont("KR", 9)
    c.drawCentredString(W/2, y, "위 계약 내용을 확인하고 2025년 7월 25일 계약을 체결한다.")
    y -= 8*mm
    sign_block(c, y,
        landlord=["성  명: 김 수 선", "주  소: 서울시 노원구 중계동 77", "연락처: 010-9999-5555"],
        tenant= ["성  명: 최 안 심", "주  소: 서울시 성북구 성북동 3", "연락처: 010-5555-4444"],
    )
    footer(c); c.save(); print(f"✅ {fname}")


# ── 실행 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    make_05()
    make_06()
    make_07()
    make_08()
    print()
    print("=" * 62)
    print("추가 테스트 계약서 4종 생성 완료")
    print("=" * 62)
    print("  05: 월세 위험  — 차임 일방 인상 + 불법 자력구제 + 갱신권 포기")
    print("  06: 오피스텔 위험 — 전입신고 금지 + 세무손해 임차인 전가")
    print("  07: 전세사기 위험 — 신탁 미동의 + 대항력 무력화 (실제 사기 패턴)")
    print("  08: 월세 정상  — 수선 임대인 부담 + 중도해지 위약금 없음")
    print()
    print("예상 분석 결과:")
    print("  05 → 🚨 위험  (high 2개 + medium 3개)")
    print("  06 → 🚨 위험  (고위험 전입신고 금지 + 확정일자 포기)")
    print("  07 → 🚨 위험  (전세사기 패턴 고위험 6개)")
    print("  08 → ✅ 정상  (위험 조항 없음)")
