"""조항별 위험 분류 품질 측정 — test_contracts/*.pdf (한글 파일명 라벨).

measure_ai_quality.py(문서 등급 정확도)의 보완판.
정상/위험 정답을 파일명에서 읽고, 조항별 위험 분류 + 문서 등급을 출력한다.
실제 backend.ai 모듈을 import 하므로 KLUE-RoBERTa 모델이 로드되면 모델 경로까지 측정된다.

PDF 텍스트는 프로젝트 OCR 경로(ai.ocr.run_ocr → 디지털 PDF는 pdfplumber)로 추출하므로
컨테이너에 별도 바이너리(poppler 등) 설치가 필요 없다.

실행 (docker, 프로젝트 루트):
  # 리포지토리 루트를 /work 로 마운트해서 backend/·test_contracts/ 를 찾게 한다.
  docker compose run --rm --no-deps -v "$PWD:/work" -w /work backend \
    python scripts/measure_clause_risk.py
  # Git Bash(MSYS)에서 경로가 C:/Program Files/Git/work 로 변환되면
  # 앞에 MSYS_NO_PATHCONV=1 을 붙이거나 PowerShell에서 실행한다.
"""
import os
import sys
import glob

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backend"))

from ai.ocr import run_ocr                           # noqa: E402
from ai.clause_parser import parse_clauses          # noqa: E402
from ai.classifier import classify_risk             # noqa: E402
try:
    from ai.pipeline import _detect_contract_type   # noqa: E402
except Exception:  # pragma: no cover
    import re
    def _detect_contract_type(text: str) -> str:
        n = re.sub(r"\s+", " ", text)
        m = re.search(r"(?:월세|차임)\D{0,15}([\d,]{3,})\s*원", n)
        if m and int(m.group(1).replace(",", "")) > 0:
            return "monthly"
        if any(k in n for k in ("전세", "전세금", "전세보증금")):
            return "jeonse"
        return "monthly" if ("월세" in n or "차임" in n) else "unknown"

_DIR = os.path.join(_ROOT, "test_contracts")
_EMO = {"high": "🚨", "medium": "🟠", "caution": "🟡", "safe": "✅"}


def _grade(s: dict) -> str:
    high, medium, caution = s["high"], s["medium"], s["caution"]
    if high >= 1 or medium >= 2:
        return "high"
    if medium == 1 or caution >= 1:
        return "caution"
    return "safe"


def _read_pdf_text(path: str) -> str:
    with open(path, "rb") as f:
        data = f.read()
    return run_ocr(data, "application/pdf").get("raw_text", "")


def main() -> int:
    pdfs = sorted(glob.glob(os.path.join(_DIR, "*.pdf")))
    if not pdfs:
        print(f"테스트 계약서 없음: {_DIR}")
        return 1
    tg = tc = gg = gc = 0
    for pdf in pdfs:
        name = os.path.basename(pdf)
        text = _read_pdf_text(pdf)
        ctype = _detect_contract_type(text)
        clauses = classify_risk(parse_clauses(text))
        s = {"high": 0, "medium": 0, "caution": 0, "safe": 0}
        flagged = []
        for c in clauses:
            r = c.get("risk", "safe")
            s[r] = s.get(r, 0) + 1
            if r != "safe":
                flagged.append(f"{_EMO[r]}{c.get('number', '?')}")
        g = _grade(s)
        exp_t = "jeonse" if ("전세" in name and "반전세" not in name) else "monthly"
        # 정답 등급: 파일명의 정상/주의/위험 토큰
        exp_g = "safe" if "정상" in name else ("caution" if "주의" in name else "high")
        t_ok = ctype == exp_t
        g_ok = (g == exp_g)  # 정확 일치(과탐/미탐 모두 실패로 본다)
        tc += 1; tg += int(t_ok); gc += 1; gg += int(g_ok)
        print(f"{'OK' if g_ok else 'XX'} {name}")
        print(f"   유형 {ctype}/{exp_t}{'✓' if t_ok else '✗'}  등급 {g}/{exp_g}{'✓' if g_ok else '✗'}  {s}")
        print(f"   위험표시: {' '.join(flagged) if flagged else '(없음)'}")
    print("-" * 70)
    print(f"유형 감지 {tg}/{tc} ({tg/tc*100:.0f}%)   문서 등급 {gg}/{gc} ({gg/gc*100:.0f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
