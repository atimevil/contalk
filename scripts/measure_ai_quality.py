"""
AI 분석 품질 측정 — 실제 테스트 계약서 대상.

측정 항목 (OpenAI API 호출 없음):
  1. 계약 유형 감지 (_detect_contract_type) 정확도
  2. 위험도 등급 분류 (classifier → _compute_risk_level) 정확도

정답 라벨은 파일명에서 파싱한다 (예: contract_01_jeonse_danger.pdf → jeonse, high).
OCR은 디지털 PDF의 pdfplumber 경로만 사용하므로 GPT 호출이 없다 (RAG도 호출 안 함).

실행 (docker):
  docker compose run --rm --no-deps -w /work -v <root>:/work backend \
    python scripts/measure_ai_quality.py
"""
import os
import sys
import glob

# backend 패키지 import 경로
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backend"))

from ai.ocr import run_ocr  # noqa: E402
from ai.pipeline import _detect_contract_type  # noqa: E402
from ai.clause_parser import parse_clauses  # noqa: E402
from ai.classifier import classify_risk  # noqa: E402

_CONTRACTS_DIR = os.path.join(_ROOT, "tests", "contracts")


def _compute_risk_level(summary: dict) -> str:
    """contract_service._compute_risk_level 과 동일한 등급 산출.

    app(pydantic/sqlalchemy) 의존 없이 학습 환경에서 독립 실행하도록 인라인했다.
    원본과 로직이 바뀌면 양쪽을 함께 수정할 것.
    """
    high = summary.get("high", 0)
    medium = summary.get("medium", 0)
    caution = summary.get("caution", 0)
    if high >= 1 or medium >= 2:
        return "high"
    if medium == 1 or caution >= 1:
        return "caution"
    return "safe"


def expected_type(name: str):
    """파일명에서 기대 계약 유형. jeonse/monthly 단어 없으면 None(채점 제외)."""
    if "monthly" in name:
        return "monthly"
    if "jeonse" in name:
        return "jeonse"
    return None


def expected_level(name: str):
    """파일명에서 기대 위험 등급 (high/caution/safe/medium)."""
    if any(k in name for k in ("danger", "gaptrade", "sagi")):
        return "high"
    if "caution" in name:
        return "caution"
    if "medium" in name:
        return "medium"  # 등급제는 high/caution/safe 3단계 → caution|high 허용
    if any(k in name for k in ("safe", "normal")):
        return "safe"
    return None


def main():
    pdfs = sorted(glob.glob(os.path.join(_CONTRACTS_DIR, "contract_*.pdf")))
    if not pdfs:
        print(f"테스트 계약서를 찾을 수 없습니다: {_CONTRACTS_DIR}")
        return 1

    type_correct = type_total = 0
    level_correct = level_total = 0
    rows = []

    for pdf in pdfs:
        name = os.path.basename(pdf)
        with open(pdf, "rb") as f:
            data = f.read()

        ocr = run_ocr(data, "application/pdf")
        text = ocr.get("raw_text", "")
        method = ocr.get("method", "?")

        ctype = _detect_contract_type(text)
        clauses = parse_clauses(text)
        classified = classify_risk(clauses)

        summary = {"high": 0, "medium": 0, "caution": 0, "safe": 0}
        for c in classified:
            r = c.get("risk", "safe")
            summary[r] = summary.get(r, 0) + 1
        level = _compute_risk_level(summary)

        exp_t = expected_type(name)
        exp_l = expected_level(name)

        t_ok = (exp_t is None) or (ctype == exp_t)
        if exp_l == "medium":
            l_ok = level in ("caution", "high")
        else:
            l_ok = (exp_l is None) or (level == exp_l)

        if exp_t is not None:
            type_total += 1
            type_correct += int(t_ok)
        if exp_l is not None:
            level_total += 1
            level_correct += int(l_ok)

        rows.append((name, method, ctype, exp_t, t_ok, level, exp_l, l_ok, summary, len(clauses)))

    # ── 출력 ──────────────────────────────────────────────────────────────────
    print("=" * 100)
    print(f"AI 분석 품질 측정 — {len(pdfs)}개 계약서 (OpenAI 호출 없음)")
    print("=" * 100)
    hdr = f"{'파일':<38}{'OCR':<11}{'유형(감지/기대)':<22}{'등급(산출/기대)':<22}{'조항':<5}"
    print(hdr)
    print("-" * 100)
    for name, method, ctype, exp_t, t_ok, level, exp_l, l_ok, summary, n in rows:
        tmark = "✓" if t_ok else "✗"
        lmark = "✓" if l_ok else "✗"
        type_col = f"{ctype}/{exp_t or '-'} {tmark}"
        level_col = f"{level}/{exp_l or '-'} {lmark}"
        print(f"{name:<38}{method:<11}{type_col:<22}{level_col:<22}{n:<5}")
        print(f"{'':<38}{'':<11}summary={summary}")

    print("-" * 100)
    t_pct = (type_correct / type_total * 100) if type_total else 0.0
    l_pct = (level_correct / level_total * 100) if level_total else 0.0
    print(f"계약 유형 감지 정확도: {type_correct}/{type_total} ({t_pct:.0f}%)")
    print(f"위험 등급 분류 정확도: {level_correct}/{level_total} ({l_pct:.0f}%)")
    print("=" * 100)
    return 0


if __name__ == "__main__":
    sys.exit(main())
