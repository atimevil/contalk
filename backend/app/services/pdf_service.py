"""PDF generation for analysis results and special clauses."""
from io import BytesIO
from datetime import datetime, timezone
from typing import List

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.schemas.common import DISCLAIMER


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


def generate_analysis_pdf(report_id: str, result_data: dict) -> bytes:
    """Generate a PDF analysis report and return bytes."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=18, spaceAfter=12)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=14, spaceAfter=8)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, spaceAfter=6, leading=14)
    disclaimer_style = ParagraphStyle(
        "Disclaimer", parent=styles["Normal"], fontSize=8, textColor=colors.grey, spaceAfter=6
    )

    story = []

    # Title
    story.append(Paragraph("계약서 분석 결과", title_style))
    story.append(Paragraph(f"보고서 ID: {report_id}", body_style))
    story.append(Paragraph(
        f"생성일: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC", body_style
    ))
    story.append(Spacer(1, 0.5 * cm))

    # Summary table
    summary = result_data.get("summary", {})
    story.append(Paragraph("위험 조항 요약", heading_style))
    summary_data = [
        ["구분", "개수"],
        ["고위험", str(summary.get("high", 0))],
        ["중위험", str(summary.get("medium", 0))],
        ["주의", str(summary.get("caution", 0))],
        ["정상", str(summary.get("safe", 0))],
    ]
    tbl = Table(summary_data, colWidths=[8 * cm, 4 * cm])
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
        ])
    )
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))

    # Clauses
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

    # Disclaimer
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(DISCLAIMER, disclaimer_style))

    doc.build(story)
    return buffer.getvalue()


def generate_special_clauses_pdf(report_id: str, clauses: list) -> bytes:
    """Generate a PDF for recommended special clauses."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("Title", parent=styles["Title"], fontSize=18, spaceAfter=12)
    heading_style = ParagraphStyle("Heading", parent=styles["Heading2"], fontSize=14, spaceAfter=8)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10, spaceAfter=6, leading=14)
    disclaimer_style = ParagraphStyle(
        "Disclaimer", parent=styles["Normal"], fontSize=8, textColor=colors.grey, spaceAfter=6
    )

    story = []
    story.append(Paragraph("추천 특약사항", title_style))
    story.append(Paragraph(f"보고서 ID: {report_id}", body_style))
    story.append(Spacer(1, 0.5 * cm))

    for clause in clauses:
        story.append(Paragraph(f"<b>{clause.get('title', '')}</b>", heading_style))
        story.append(Paragraph(clause.get("text", ""), body_style))
        story.append(Spacer(1, 0.3 * cm))

    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(DISCLAIMER, disclaimer_style))

    doc.build(story)
    return buffer.getvalue()
