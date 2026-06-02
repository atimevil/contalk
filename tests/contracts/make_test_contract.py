"""
계약똑똑 테스트용 전세 계약서 PDF 생성기

분류기 패턴별 위험 조항:
  medium  — 임대인 동의 없이, 보증금 반환 거절, 원상복구, 수선 책임, 중도해지 위약금, 임의방문
  caution — 전대 금지, 반려동물, 흡연 금지, 인테리어 변경 금지
  safe    — 기본 임대차 조항, 기간, 목적
"""

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
import os, sys

# 스크립트 위치 기준으로 PDF 출력 (어디서 실행하든 이 파일 옆에 생성)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# ── 한글 폰트 등록 ──────────────────────────────────────────────────────────
FONT_CANDIDATES = [
    "C:/Windows/Fonts/malgun.ttf",       # 맑은 고딕 (Windows)
    "C:/Windows/Fonts/NanumGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    "/System/Library/Fonts/AppleSDGothicNeo-Regular.otf",
]

font_path = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
if font_path is None:
    print("❌ 한글 폰트를 찾을 수 없습니다. 맑은 고딕이 필요합니다.")
    sys.exit(1)

pdfmetrics.registerFont(TTFont("Korean", font_path))
print(f"✅ 폰트 로드: {font_path}")

# ── 계약서 내용 ──────────────────────────────────────────────────────────────

CONTRACT_LINES = [
    ("title",  "주택 임대차 계약서 (전세)"),
    ("blank",  ""),
    ("body",   "임대인 홍길동(이하 '임대인')과 임차인 김철수(이하 '임차인')는 아래 표시 부동산에"),
    ("body",   "관하여 다음과 같이 임대차 계약을 체결한다."),
    ("blank",  ""),
    ("section","【부동산 표시】"),
    ("body",   "소 재 지: 서울특별시 노원구 상계동 123-45, 현대4차아파트 101동 502호"),
    ("body",   "구조/면적: 철근콘크리트조, 전용면적 84.73㎡"),
    ("body",   "보증금: 금 이억오천만원정 (\\250,000,000원)"),
    ("blank",  ""),
    ("section","제1조 (목적)"),
    ("body",   "본 계약은 위 표시 부동산에 대한 임대차 계약을 체결함을 목적으로 한다."),   # safe
    ("blank",  ""),
    ("section","제2조 (임대차 기간)"),
    ("body",   "임대차 기간은 2025년 7월 1일부터 2027년 6월 30일까지 24개월로 한다."),     # safe
    ("blank",  ""),
    ("section","제3조 (보증금 납부)"),
    ("body",   "임차인은 계약 체결 시 계약금 2,500만원을 납부하고, 잔금 222,500만원은"),
    ("body",   "2025년 6월 30일까지 납부한다."),                                           # safe
    ("blank",  ""),
    ("section","제4조 (사용 제한)"),                                                       # caution × 3
    ("body",   "① 임차인은 임대인의 사전 서면 동의 없이 목적물을 전대하거나 임차권을 양도할 수 없다."),
    ("body",   "② 반려동물 사육 및 애완동물 양육은 임대인 동의 없이 금지한다."),
    ("body",   "③ 건물 내 흡연은 금지한다."),
    ("blank",  ""),
    ("section","제5조 (임차인의 의무)"),
    ("body",   "① 임차인은 선량한 관리자의 주의로 목적물을 관리하여야 한다."),              # safe
    ("body",   "② 임차인은 임대인의 동의 없이 인테리어·구조 변경 및 공사를 금지한다."),     # caution
    ("body",   "③ 계약 종료 시 원상복구 의무를 지며, 복구 비용은 임차인이 전액 부담한다."), # medium
    ("blank",  ""),
    ("section","제6조 (수선 책임)"),                                                       # medium
    ("body",   "목적물의 수선 책임 및 비용은 사유를 불문하고 임차인이 전액 부담한다."),
    ("body",   "단, 천재지변으로 인한 경우는 제외한다."),
    ("blank",  ""),
    ("section","제7조 (관리비)"),                                                          # medium
    ("body",   "관리비는 임차인이 전액 부담하며, 미납 시 보증금에서 우선 공제한다."),
    ("blank",  ""),
    ("section","제8조 (임대인의 출입)"),                                                   # medium
    ("body",   "임대인은 목적물 유지·관리를 위해 언제든지 사전 통보 없이 방문 및 출입할 수 있다."),
    ("blank",  ""),
    ("section","제9조 (중도 해지)"),                                                       # medium
    ("body",   "① 임차인이 중도 해지할 경우 보증금의 10%를 위약금·손해배상으로 임대인에게 지급한다."),
    ("body",   "② 임대인은 언제든지 일방적으로 계약을 해지할 수 있으며, 이 경우 임차인은"),
    ("body",   "   해지 통보 후 30일 이내에 퇴거하여야 한다."),
    ("blank",  ""),
    ("section","제10조 (연체 이자)"),                                                      # medium
    ("body",   "임차인이 차임 또는 관리비를 2회 이상 연체할 경우 연체 이율 연 15%의"),
    ("body",   "이자를 가산하며, 임대인은 즉시 계약을 해지할 수 있다."),
    ("blank",  ""),
    ("section","제11조 (보증금 반환)"),
    ("body",   "① 임대인은 계약 만료 시 임차인의 원상복구 이행 확인 후 30일 이내에"),      # medium → caution 혼재
    ("body",   "   보증금을 반환한다."),
    ("body",   "② 임대인의 귀책으로 보증금 반환이 지연될 경우 연 12%의 지연이자를 가산한다."), # caution (임차인 보호)
    ("body",   "③ 임차인의 채무 불이행이 있는 경우 임대인은 보증금 반환을 거절할 수 있다."), # medium
    ("blank",  ""),
    ("section","제12조 (대항력 및 확정일자)"),
    ("body",   "임차인은 전입신고를 제한 없이 할 수 있으며, 확정일자 신청 권리를 보유한다."), # safe
    ("blank",  ""),
    ("section","【특약사항】"),
    ("body",   "1. 본 계약 체결 전 임차인은 등기부등본을 직접 확인하였음."),
    ("body",   "2. 세탁기·에어컨 추가 설치는 임대인 서면 동의 후 가능하다."),              # caution
    ("body",   "3. 계약 기간 중 임차인은 계약 해지를 할 수 없으며, 부득이한 경우"),         # medium
    ("body",   "   위약금 규정(제9조)을 따른다."),
    ("body",   "4. 보증금에 대한 이자는 발생하지 않으며 임대인은 이를 지급하지 아니한다."), # medium
    ("blank",  ""),
    ("body",   "본 계약서를 확인하고 각자 서명·날인한다."),
    ("blank",  ""),
    ("body",   "2025년  6월   일"),
    ("blank",  ""),
    ("body",   "임 대 인: 홍길동  (서명)          임 차 인: 김철수  (서명)"),
    ("body",   "주    소: 서울시 강남구 테헤란로 100  주    소: 서울시 노원구 상계동 1"),
    ("body",   "연 락 처: 010-1234-5678            연 락 처: 010-9876-5432"),
]

# ── PDF 생성 ──────────────────────────────────────────────────────────────────

OUTPUT = "test_contract.pdf"
W, H = A4          # 595.27 × 841.89 pt
MARGIN_X = 20 * mm
MARGIN_TOP = 25 * mm
MARGIN_BOTTOM = 20 * mm

c = canvas.Canvas(OUTPUT, pagesize=A4)
y = H - MARGIN_TOP

def new_page():
    global y
    c.showPage()
    y = H - MARGIN_TOP

def draw_line(kind, text):
    global y
    if y < MARGIN_BOTTOM + 10 * mm:
        new_page()

    if kind == "blank":
        y -= 6
        return

    if kind == "title":
        c.setFont("Korean", 16)
        c.setFillColorRGB(0.1, 0.1, 0.1)
        tw = c.stringWidth(text, "Korean", 16)
        c.drawString((W - tw) / 2, y, text)
        y -= 30
        # 구분선
        c.setStrokeColorRGB(0.3, 0.3, 0.3)
        c.line(MARGIN_X, y + 5, W - MARGIN_X, y + 5)
        y -= 4
        return

    if kind == "section":
        if y < H - MARGIN_TOP - 5:  # 맨 위가 아니면 위 여백 추가
            y -= 8
        c.setFont("Korean", 11)
        c.setFillColorRGB(0.08, 0.35, 0.72)   # 파란색 강조
        c.drawString(MARGIN_X, y, text)
        y -= 16
        return

    # body
    c.setFont("Korean", 10)
    c.setFillColorRGB(0.1, 0.1, 0.1)
    # 들여쓰기 (①② 번호 조항은 추가 들여쓰기)
    indent = MARGIN_X + (4 * mm if text.lstrip().startswith(("①","②","③","1.","2.","3.","4.")) else 0)
    c.drawString(indent, y, text)
    y -= 15

for kind, text in CONTRACT_LINES:
    draw_line(kind, text)

c.save()
print(f"\n✅ 계약서 생성 완료: {OUTPUT}")
print(f"   경로: {os.path.abspath(OUTPUT)}")
print()
print("📋 포함된 위험 조항 요약:")
print("  🔴 medium  — 원상복구(5조③), 수선비 임차인 부담(6조), 관리비 전액(7조),")
print("               임대인 언제든지 방문(8조), 중도해지 위약금+임대인 일방해지(9조),")
print("               연체이율 연15%(10조), 보증금 반환 거절(11조③), 계약해지 불가(특약3)")
print("               보증금 이자 없음(특약4)")
print("  🟡 caution — 전대금지(4조①), 반려동물 금지(4조②), 흡연금지(4조③),")
print("               인테리어 변경 금지(5조②), 세탁기·에어컨 설치 제한(특약2),")
print("               보증금 반환 지연이자 가산(11조②, 임차인 보호 → caution)")
print("  ✅ safe    — 목적(1조), 기간(2조), 보증금 납부(3조), 관리자 의무(5조①),")
print("               전입신고·확정일자 보장(12조)")
