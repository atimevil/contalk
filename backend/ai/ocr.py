"""
OCR 모듈 — GPT-4o Vision 기반 텍스트 추출

우선순위:
    0. 텍스트 파일 → 직접 읽기 (개발/테스트 환경)
    1. 디지털 PDF → pdfplumber (무료, API 호출 없음)
    2. 스캔 PDF → PyMuPDF 페이지 이미지 변환 → GPT-4o Vision
    3. 이미지 (JPEG/PNG/WEBP 등) → GPT-4o Vision
"""
from __future__ import annotations

import base64
import io
import logging
import os
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

_OCR_PROMPT = (
    "다음 이미지는 한국어 임대차 계약서입니다. "
    "이미지에 있는 모든 텍스트를 정확하게 추출해주세요. "
    "줄바꿈과 문단 구조를 최대한 유지하고, "
    "조항 번호(제1조, 제2조 등)와 특약사항 항목을 그대로 보존해주세요. "
    "텍스트만 출력하고 다른 설명은 하지 마세요."
)


# ---------------------------------------------------------------------------
# 공개 인터페이스
# ---------------------------------------------------------------------------

def run_ocr(file_bytes: bytes, content_type: str) -> dict:
    """
    계약서 파일에서 텍스트를 추출한다.

    Parameters
    ----------
    file_bytes : bytes
        파일 바이너리
    content_type : str
        MIME 타입. "application/pdf", "image/jpeg", "image/png", "text/plain" 등

    Returns
    -------
    dict
        {
            "raw_text":   str,
            "confidence": float,
            "method":     str,  # "plain_text" | "pdfplumber" | "gpt4o_vision" | "gpt4o_vision_pdf"
        }
    """
    if not file_bytes:
        raise ValueError("file_bytes가 비어 있습니다.")

    # ── 0. 텍스트 파일 직접 읽기 (개발/테스트) ───────────────────────────────
    if content_type in ("text/plain", "text/txt") or _is_text_bytes(file_bytes):
        return _read_plain_text(file_bytes)

    is_pdf = content_type == "application/pdf" or _is_pdf_bytes(file_bytes)

    if is_pdf:
        # ── 1. 디지털 PDF → pdfplumber ──────────────────────────────────────
        result = _try_pdfplumber(file_bytes)
        if result and result["raw_text"].strip():
            return result

        # ── 2. 스캔 PDF → 이미지 변환 → GPT-4o Vision ───────────────────────
        logger.info(
            "pdfplumber 텍스트 없음 (스캔 PDF로 판단) → GPT-4o Vision 재시도"
        )
        return _pdf_via_gpt4o_vision(file_bytes)

    # ── 3. 이미지 → GPT-4o Vision ────────────────────────────────────────────
    return _image_via_gpt4o_vision(file_bytes, content_type)


# ---------------------------------------------------------------------------
# 헬퍼 — 파일 타입 감지
# ---------------------------------------------------------------------------

def _is_pdf_bytes(data: bytes) -> bool:
    """파일 시그니처로 PDF 여부 판단."""
    return data[:4] == b"%PDF"


def _is_text_bytes(data: bytes) -> bool:
    """바이너리 헤더가 없으면 텍스트 파일로 판단."""
    binary_signatures = (
        b"%PDF",        # PDF
        b"\xff\xd8\xff",  # JPEG
        b"\x89PNG",     # PNG
        b"II*\x00",     # TIFF LE
        b"MM\x00*",     # TIFF BE
        b"RIFF",        # WEBP
    )
    for sig in binary_signatures:
        if data[:len(sig)] == sig:
            return False
    try:
        data[:512].decode("utf-8")
        return True
    except (UnicodeDecodeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# 텍스트 파일 직접 읽기
# ---------------------------------------------------------------------------

def _read_plain_text(file_bytes: bytes) -> dict:
    """UTF-8 / EUC-KR / CP949 순서로 디코딩한다."""
    for encoding in ("utf-8", "euc-kr", "cp949"):
        try:
            text = file_bytes.decode(encoding).strip()
            logger.info(
                "텍스트 파일 직접 읽기 완료 (encoding=%s, %d자)", encoding, len(text)
            )
            return {"raw_text": text, "confidence": 1.0, "method": "plain_text"}
        except (UnicodeDecodeError, ValueError):
            continue
    raise RuntimeError("텍스트 파일 인코딩 인식 불가 (UTF-8, EUC-KR, CP949 모두 실패)")


# ---------------------------------------------------------------------------
# pdfplumber — 디지털 PDF
# ---------------------------------------------------------------------------

def _try_pdfplumber(file_bytes: bytes) -> Optional[dict]:
    """pdfplumber로 디지털 PDF 텍스트를 추출한다."""
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
            logger.warning("pdfplumber: 추출 텍스트 없음 (스캔 PDF)")
            return None

        logger.info("pdfplumber OCR 완료: %d자", len(full_text))
        return {"raw_text": full_text, "confidence": 0.95, "method": "pdfplumber"}

    except ImportError:
        logger.warning("pdfplumber 미설치")
        return None
    except Exception as exc:
        logger.warning("pdfplumber 처리 실패: %s", exc)
        return None


# ---------------------------------------------------------------------------
# GPT-4o Vision — 이미지
# ---------------------------------------------------------------------------

def _image_via_gpt4o_vision(file_bytes: bytes, content_type: str) -> dict:
    """이미지 파일을 GPT-4o Vision으로 OCR한다."""
    _require_openai_key()

    # TIFF → JPEG 변환 (GPT-4o 미지원 포맷)
    if content_type in ("image/tiff", "image/tif"):
        file_bytes, content_type = _convert_tiff_to_jpeg(file_bytes)

    supported = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif"}
    if content_type not in supported:
        raise RuntimeError(
            f"지원하지 않는 이미지 형식: {content_type}. "
            "지원 형식: JPEG, PNG, WEBP, GIF, TIFF"
        )

    b64 = base64.b64encode(file_bytes).decode()
    text = _call_gpt4o_vision(b64, content_type)
    logger.info("GPT-4o Vision OCR 완료: %d자", len(text))

    return {"raw_text": text, "confidence": 0.93, "method": "gpt4o_vision"}


# ---------------------------------------------------------------------------
# GPT-4o Vision — 스캔 PDF (PyMuPDF로 페이지 이미지 변환)
# ---------------------------------------------------------------------------

def _pdf_via_gpt4o_vision(file_bytes: bytes) -> dict:
    """
    스캔 PDF를 페이지별 PNG로 변환 후 GPT-4o Vision으로 OCR한다.
    PyMuPDF(fitz) 필요: pip install pymupdf
    """
    _require_openai_key()

    try:
        import fitz  # PyMuPDF  # type: ignore
    except ImportError:
        raise RuntimeError(
            "스캔 PDF 처리를 위해 PyMuPDF가 필요합니다.\n"
            "pip install pymupdf"
        )

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        all_text: list[str] = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            # 150 DPI 수준 (Matrix 1.5 = 72dpi × 1.5 ≈ 108dpi, 품질/속도 균형)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            img_bytes = pix.tobytes("png")

            b64 = base64.b64encode(img_bytes).decode()
            page_text = _call_gpt4o_vision(b64, "image/png")

            if page_text.strip():
                all_text.append(page_text)

            logger.info(
                "스캔 PDF 페이지 %d/%d OCR 완료 (%d자)",
                page_num + 1, len(doc), len(page_text),
            )

        doc.close()

        full_text = "\n\n".join(all_text)
        logger.info("스캔 PDF 전체 OCR 완료: %d페이지, %d자", len(all_text), len(full_text))
        return {"raw_text": full_text, "confidence": 0.92, "method": "gpt4o_vision_pdf"}

    except Exception as exc:
        raise RuntimeError(f"스캔 PDF GPT-4o Vision 처리 실패: {exc}") from exc


# ---------------------------------------------------------------------------
# GPT-4o Vision API 호출
# ---------------------------------------------------------------------------

def _call_gpt4o_vision(b64_image: str, content_type: str) -> str:
    """GPT-4o Vision API를 호출하고 추출된 텍스트를 반환한다."""
    try:
        from openai import OpenAI  # type: ignore
    except ImportError:
        raise RuntimeError("openai 패키지 미설치. pip install openai")

    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("OPENAI_MODEL", "gpt-5.4")
    logger.info("GPT Vision 호출 시작 (model=%s, key=sk-...%s)", model, api_key[-4:] if api_key else "없음")
    client = OpenAI(api_key=api_key or None)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{content_type};base64,{b64_image}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": _OCR_PROMPT},
                ],
            }
        ],
        max_completion_tokens=4096,
        temperature=0,  # OCR은 일관성 우선
    )
    return (response.choices[0].message.content or "").strip()


# ---------------------------------------------------------------------------
# 공통 헬퍼
# ---------------------------------------------------------------------------

def _require_openai_key() -> None:
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다.")


def _convert_tiff_to_jpeg(file_bytes: bytes) -> Tuple[bytes, str]:
    """TIFF를 JPEG으로 변환한다 (GPT-4o 미지원 포맷 대응)."""
    try:
        from PIL import Image  # type: ignore

        img = Image.open(io.BytesIO(file_bytes))
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=90)
        logger.info("TIFF → JPEG 변환 완료")
        return buf.getvalue(), "image/jpeg"
    except ImportError:
        raise RuntimeError("TIFF 변환을 위해 Pillow가 필요합니다. pip install Pillow")


# ---------------------------------------------------------------------------
# 독립 테스트
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    print("=== OCR 모듈 독립 테스트 ===\n")
    print(f"OPENAI_API_KEY: {'설정됨' if os.environ.get('OPENAI_API_KEY') else '미설정'}")
    print()

    # 1. 텍스트 파일 폴백 테스트
    sample = "제1조 (목적)\n본 계약은 임대차 계약을 목적으로 한다.\n\n특약사항\n반려동물 사육 금지."
    result = run_ocr(sample.encode("utf-8"), "text/plain")
    print(f"[텍스트 폴백] method={result['method']}, 길이={len(result['raw_text'])}자")

    # 2. 이미지 테스트 (이미지 파일 경로를 인수로 전달)
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        with open(img_path, "rb") as f:
            img_bytes = f.read()
        ext = img_path.rsplit(".", 1)[-1].lower()
        ct_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                  "png": "image/png", "pdf": "application/pdf"}
        ct = ct_map.get(ext, "image/jpeg")
        result = run_ocr(img_bytes, ct)
        print(f"\n[{img_path}] method={result['method']}, 신뢰도={result['confidence']}")
        print(f"추출 텍스트 (첫 300자):\n{result['raw_text'][:300]}")
    else:
        print("\n이미지/PDF 테스트: python -m backend.ai.ocr <파일경로>")

    print("\nOCR 테스트 완료.")
