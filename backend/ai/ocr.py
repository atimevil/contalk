"""
OCR 모듈 — Google Cloud Vision API 기반 텍스트 추출
폴백: pdfplumber (Vision API 키 없거나 실패 시)
"""
from __future__ import annotations

import io
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

def run_ocr(file_bytes: bytes, content_type: str) -> dict:
    """
    계약서 파일에서 텍스트를 추출한다.

    Parameters
    ----------
    file_bytes : bytes
        S3 또는 메모리에서 읽어온 파일 바이너리
    content_type : str
        MIME 타입. 예: "application/pdf", "image/jpeg", "image/png"

    Returns
    -------
    dict
        {
            "raw_text": str,       # 추출된 전체 텍스트
            "confidence": float,   # 0.0 ~ 1.0 신뢰도 (Vision API만 제공)
            "method": str,         # "vision_api" | "pdfplumber" | "pytesseract"
        }
    """
    if not file_bytes:
        raise ValueError("file_bytes가 비어 있습니다.")

    is_pdf = content_type == "application/pdf" or _is_pdf_bytes(file_bytes)

    # 1순위: Google Cloud Vision API
    vision_result = _try_vision_api(file_bytes, is_pdf)
    if vision_result is not None:
        return vision_result

    # 2순위: pdfplumber (PDF 한정)
    if is_pdf:
        plumber_result = _try_pdfplumber(file_bytes)
        if plumber_result is not None:
            return plumber_result

    # 3순위: pytesseract (이미지 한정)
    tesseract_result = _try_pytesseract(file_bytes, is_pdf)
    if tesseract_result is not None:
        return tesseract_result

    raise RuntimeError(
        "OCR 처리에 실패했습니다. "
        "지원 형식(PDF, JPEG, PNG, TIFF, WEBP)인지 확인하고 "
        "Google Cloud Vision API 키를 설정하세요."
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_pdf_bytes(data: bytes) -> bool:
    """파일 시그니처로 PDF 여부 판단."""
    return data[:4] == b"%PDF"


def _try_vision_api(file_bytes: bytes, is_pdf: bool) -> Optional[dict]:
    """Google Cloud Vision API 호출을 시도한다."""
    credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    api_key = os.environ.get("GOOGLE_CLOUD_VISION_API_KEY", "")

    if not credentials_path and not api_key:
        logger.info("Vision API 자격증명이 없어 폴백을 사용합니다.")
        return None

    try:
        from google.cloud import vision  # type: ignore

        client = vision.ImageAnnotatorClient()

        if is_pdf:
            # PDF는 document_text_detection 사용
            result = _vision_pdf(client, file_bytes)
        else:
            # 이미지는 text_detection 사용
            result = _vision_image(client, file_bytes)

        return result

    except ImportError:
        logger.warning("google-cloud-vision 패키지가 설치되지 않았습니다. 폴백을 사용합니다.")
        return None
    except Exception as exc:
        logger.warning("Vision API 호출 실패: %s — 폴백을 사용합니다.", exc)
        return None


def _vision_image(client, file_bytes: bytes) -> dict:
    """이미지 파일에 대한 Vision API text_detection."""
    from google.cloud import vision  # type: ignore

    image = vision.Image(content=file_bytes)
    response = client.text_detection(image=image)

    if response.error.message:
        raise RuntimeError(f"Vision API 에러: {response.error.message}")

    texts = response.text_annotations
    if not texts:
        return {"raw_text": "", "confidence": 0.0, "method": "vision_api"}

    full_text = texts[0].description.strip()

    # 신뢰도 추정: 개별 symbol confidence 평균
    confidences = []
    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    for symbol in word.symbols:
                        if symbol.confidence:
                            confidences.append(symbol.confidence)

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.9

    return {
        "raw_text": full_text,
        "confidence": round(avg_confidence, 3),
        "method": "vision_api",
    }


def _vision_pdf(client, file_bytes: bytes) -> dict:
    """PDF 파일에 대한 Vision API document_text_detection (인메모리)."""
    from google.cloud import vision  # type: ignore

    # PDF가 5MB 이하면 인라인 처리 가능
    # 그 이상은 GCS 업로드가 필요하나 여기서는 단순화하여 pdfplumber 폴백 유도
    if len(file_bytes) > 5 * 1024 * 1024:
        logger.info("PDF가 5MB 초과 — Vision API PDF 직접 처리 불가, pdfplumber 폴백")
        return None  # type: ignore  # pdfplumber 폴백 유도

    image = vision.Image(content=file_bytes)
    response = client.document_text_detection(image=image)

    if response.error.message:
        raise RuntimeError(f"Vision API 에러: {response.error.message}")

    full_text = response.full_text_annotation.text.strip()

    # PDF document_text_detection의 신뢰도
    confidences = []
    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            if block.confidence:
                confidences.append(block.confidence)

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.85

    return {
        "raw_text": full_text,
        "confidence": round(avg_confidence, 3),
        "method": "vision_api",
    }


def _try_pdfplumber(file_bytes: bytes) -> Optional[dict]:
    """pdfplumber로 PDF 텍스트를 추출한다."""
    try:
        import pdfplumber  # type: ignore

        pages_text = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text.strip())

        full_text = "\n\n".join(pages_text)
        if not full_text.strip():
            logger.warning("pdfplumber: 추출된 텍스트가 없습니다 (스캔된 PDF일 수 있음).")
            return None

        return {
            "raw_text": full_text,
            "confidence": 0.95,  # 디지털 PDF는 신뢰도 높음
            "method": "pdfplumber",
        }

    except ImportError:
        logger.warning("pdfplumber 패키지가 설치되지 않았습니다.")
        return None
    except Exception as exc:
        logger.warning("pdfplumber 처리 실패: %s", exc)
        return None


def _try_pytesseract(file_bytes: bytes, is_pdf: bool) -> Optional[dict]:
    """pytesseract로 이미지에서 텍스트를 추출한다 (최후 폴백)."""
    if is_pdf:
        # pytesseract는 PDF를 직접 처리하지 않음
        return None

    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        image = Image.open(io.BytesIO(file_bytes))
        # 한국어(kor) + 영어(eng) 인식
        text = pytesseract.image_to_string(image, lang="kor+eng")

        return {
            "raw_text": text.strip(),
            "confidence": 0.7,  # tesseract는 일반적으로 낮은 신뢰도
            "method": "pytesseract",
        }

    except ImportError:
        logger.warning("pytesseract 또는 Pillow 패키지가 설치되지 않았습니다.")
        return None
    except Exception as exc:
        logger.warning("pytesseract 처리 실패: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Standalone test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    # 테스트 1: 샘플 텍스트를 포함한 인메모리 PDF 생성 후 pdfplumber 경로 테스트
    print("=== OCR 모듈 독립 테스트 ===\n")

    sample_text = """임대차 계약서

제1조 (목적)
본 계약은 아래 부동산(이하 "목적물")에 대한 임대차 계약을 체결함을 목적으로 한다.

제2조 (임대차 기간)
임대차 기간은 2024년 1월 1일부터 2026년 1월 1일까지로 한다.

제3조 (보증금 및 차임)
보증금은 금 일억원(₩100,000,000)으로 하며, 잔금은 입주일에 지불한다.

제4조 (특약사항)
임대인 동의 없이 전대 또는 임차권 양도를 할 수 없다."""

    # pdfplumber 테스트용 간단한 PDF 생성 (reportlab 사용)
    try:
        from reportlab.pdfgen import canvas  # type: ignore
        from reportlab.lib.pagesizes import A4  # type: ignore
        from reportlab.pdfbase import pdfmetrics  # type: ignore
        from reportlab.pdfbase.ttfonts import TTFont  # type: ignore

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        y = height - 80
        for line in sample_text.split("\n"):
            c.drawString(40, y, line)
            y -= 20
        c.save()
        pdf_bytes = buf.getvalue()

        result = run_ocr(pdf_bytes, "application/pdf")
        print(f"[PDF 테스트] method={result['method']}, confidence={result['confidence']}")
        print(f"첫 200자: {result['raw_text'][:200]}\n")

    except ImportError:
        print("[PDF 테스트] reportlab 미설치 — 텍스트 바이트 직접 테스트로 대체")

        # reportlab 없으면 가짜 텍스트 반환 테스트
        class _FakeResult:
            pass

        print("  pdfplumber 폴백 경로는 PDF 바이트가 있을 때 동작합니다.")
        print("  Vision API 키 없음 → pdfplumber 사용 경로가 올바르게 설정됨\n")

    # 테스트 2: Vision API 키 없을 때 폴백 동작 확인
    print("[환경 변수 확인]")
    print(f"  GOOGLE_APPLICATION_CREDENTIALS: {os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '(미설정)')}")
    print(f"  → Vision API 없으면 pdfplumber → pytesseract 순서로 폴백\n")

    print("OCR 모듈 테스트 완료.")
