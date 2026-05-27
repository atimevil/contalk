"""PDF generation for analysis results and special clauses."""
from io import BytesIO
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.schemas.common import DISCLAIMER


# ─── 한글 폰트 등록 ───────────────────────────────────────────────────────────
_NANUM_PATHS = [
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",   # Debian fonts-nanum
    "/usr/share/fonts/nanum/NanumGothic.ttf",
]

_KOREAN_FONT = "Helvetica"  # 폴백 (한글 깨질 수 있음)

for _path in _NANUM_PATHS:
    if Path(_path).exists():
        try:
            pdfmetrics.registerFont(TTFont("NanumGothic", _path))
            _KOREAN_FONT = "NanumGothic"
        except Exception:
            pass
        break


RISK_COLORS = {
    "high": colors.HexColor("#FF4444"),
    "medium": colors.HexColor("#FF8800"),
    "caution": colors.HexColor("#FFCC00"),
    "safe": colors.HexColor("#44BB44"),
}

RISK_LABELS = {
    "high": "고위험",
    "medium": "중위험",
    "caution": "주의",
    "safe": "정상",
}


def _make_styles():
    """한글 폰트가 적용된 스타일 세트 반환."""
    base = getSampleStyleSheet()
    f = _KOREAN_FONT

    title_style = ParagraphStyle(
        "KTitle", parent=base["Title"], fontName=f, fontSize=18, spaceAfter=12
    )
    heading_style = ParagraphStyle(
        "KHeading", parent=base["Heading2"], fontName=f, fontSize=14, spaceAfter=8
    )
    body_style = ParagraphStyle(
        "KBody", parent=base["Normal"], fontName=f, fontSize=10, spaceAfter=6, leading=16
    )
    disclaimer_style = ParagraphStyle(
        "KDisclaimer", parent=base["Normal"], fontName=f,
        fontSize=8, textColor=colors.grey, spaceAfter=6
    )
    return title_style, heading_style, body_style, disclaimer_style


def generate_analysis_pdf(report_id: str, result_data: dict) -> bytes:
    """계약서 분석 결과 PDF 생성."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    title_style, heading_style, body_style, disclaimer_style = _make_styles()

    story = []

    # 제목
    story.append(Paragraph("계약서 분석 결과", title_style))
    story.append(Paragraph(f"보고서 ID: {report_id}", body_style))
    story.append(Paragraph(
        f"생성일: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC", body_style
    ))
    story.append(Spacer(1, 0.5 * cm))

    # 요약 테이블
    summary = result_data.get("summary", {})
    story.append(Paragraph("위험 조항 요약", heading_style))
    summary_data = [
        ["구분", "개수"],
        ["고위험", str(summary.get("high", 0))],
        ["중위험", str(summary.get("medium", 0))],
        ["주의", str(summary.get("caution", 0))],
        ["정상", str(summary.get("safe", 0))],
    ]
    # 테이블 셀도 한글 폰트 적용
    from reportlab.platypus import Paragraph as P
    summary_data_p = []
    for row in summary_data:
        summary_data_p.append([P(cell, body_style) for cell in row])

    tbl = Table(summary_data_p, colWidths=[8 * cm, 4 * cm])
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ])
    )
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))

    # 조항별 분석
    clauses = result_data.get("clauses", [])
    if clauses:
        story.append(Paragraph("조항별 분석", heading_style))
        for c in clauses:
            risk = c.get("risk", "safe")
            risk_label = RISK_LABELS.get(risk, risk)
            clause_num = c.get("clause_number", "")
            prefix = f"[{risk_label}] {clause_num}".strip()

            story.append(Paragraph(f"<b>{prefix}</b>", body_style))
            story.append(Paragraph(f"원문: {c.get('original_text', '')}", body_style))
            story.append(Paragraph(f"설명: {c.get('explanation', '')}", body_style))
            if c.get("recommendation"):
                story.append(Paragraph(f"권고사항: {c['recommendation']}", body_style))
            story.append(Spacer(1, 0.3 * cm))

    # 면책 고지
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(DISCLAIMER, disclaimer_style))

    doc.build(story)
    return buffer.getvalue()


def generate_special_clauses_pdf(report_id: str, clauses: list) -> bytes:
    """추천 특약사항 PDF 생성."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    title_style, heading_style, body_style, disclaimer_style = _make_styles()

    story = []
    story.append(Paragraph("추천 특약사항", title_style))
    story.append(Spacer(1, 0.5 * cm))

    for clause in clauses:
        story.append(Paragraph(f"<b>{clause.get('title', '')}</b>", heading_style))
        story.append(Paragraph(clause.get("text", ""), body_style))
        story.append(Spacer(1, 0.3 * cm))

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(DISCLAIMER, disclaimer_style))

    doc.build(story)
    return buffer.getvalue()
