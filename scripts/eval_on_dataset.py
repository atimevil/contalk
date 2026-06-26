"""실데이터(조항 단위) 분류 정확도 측정 — data/val.jsonl 대상.

val.jsonl 각 행: {"text": <조항 원문>, "label": "safe|caution|medium", "label_id": int}
실제 backend.ai.classifier.classify_risk 를 호출하므로,
KLUE_ROBERTA_MODEL_PATH 가 설정돼 모델이 로드되면 **모델 경로(실서비스)** 정확도를,
미설정이면 룰 폴백 정확도를 측정한다.

데이터셋은 3-class(safe/caution/medium)이고 high가 없으므로,
분류기의 high(치명 위험 규칙 승격)는 medium 으로 매핑해 비교한다.

실행 (docker, 프로젝트 루트):
  docker compose run --rm --no-deps -v "$PWD:/work" -w /work \
    -e KLUE_ROBERTA_MODEL_PATH=/work/models/roberta_risk_classifier \
    backend python scripts/eval_on_dataset.py
  # 모델 경로 미지정 시 룰 폴백으로 측정된다.

평가셋 선택 (EVAL_DATASET, 기본 data/val.jsonl):
  모델(KLUE-RoBERTa)은 GPT 재라벨(data/*.gpt.jsonl)로 훈련되므로, 모델 품질 측정은
  라벨 기준이 일치하는 val.gpt.jsonl 로 해야 한다:
    -e EVAL_DATASET=/work/data/val.gpt.jsonl
  기본 val.jsonl(rule 라벨, caution 강제 상향)로 측정하면 라벨 불일치로 점수가 낮게
  나오며 이는 모델 결함이 아니다. (실측: val.gpt.jsonl 88.3% vs val.jsonl 20.3%)
"""
import os
import sys
import json
import collections

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backend"))

from ai.classifier import classify_risk  # noqa: E402

_DATASET = os.environ.get("EVAL_DATASET", "") or os.path.join(_ROOT, "data", "val.jsonl")
_LABELS = ["safe", "caution", "medium"]


def _norm(pred: str) -> str:
    # 데이터셋은 high 라벨이 없음 → 치명 위험(high)은 medium 으로 간주해 비교
    return "medium" if pred == "high" else pred


def main() -> int:
    if not os.path.exists(_DATASET):
        print(f"데이터셋 없음: {_DATASET}")
        return 1

    rows = [json.loads(line) for line in open(_DATASET, encoding="utf-8")]
    # 배치 분류 (classify_risk 는 조항 리스트를 받는다)
    clauses = [{"number": "X", "title": "", "text": r["text"], "items": []} for r in rows]
    preds = [_norm(c["risk"]) for c in classify_risk(clauses)]

    correct = 0
    per = collections.defaultdict(lambda: collections.Counter())
    for r, pred in zip(rows, preds):
        gold = r["label"]
        per[gold][pred] += 1
        correct += int(pred == gold)

    n = len(rows)
    model = os.environ.get("KLUE_ROBERTA_MODEL_PATH", "")
    print("=" * 64)
    print(f"실데이터 분류 정확도 — {os.path.basename(_DATASET)} {n}건")
    print(f"경로: {'모델(KLUE-RoBERTa)+규칙' if model else '규칙 폴백(모델 미설정)'}")
    print("=" * 64)
    print(f"전체 정확도: {correct}/{n} = {correct / n * 100:.1f}%\n")

    print("혼동행렬 (행=정답, 열=예측):")
    print("gold\\pred".ljust(10) + "".join(l.rjust(9) for l in _LABELS))
    for g in _LABELS:
        print(g.ljust(10) + "".join(str(per[g][p]).rjust(9) for p in _LABELS))

    print("\n클래스별 precision / recall / F1:")
    for c in _LABELS:
        tp = per[c][c]
        fp = sum(per[g][c] for g in _LABELS) - tp
        fn = sum(per[c][p] for p in _LABELS) - tp
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        print(f"  {c:<8} P={prec*100:5.1f}%  R={rec*100:5.1f}%  F1={f1*100:5.1f}%  (n={sum(per[c].values())})")

    # 매크로 F1 (클래스 불균형 보정 지표)
    f1s = []
    for c in _LABELS:
        tp = per[c][c]; fp = sum(per[g][c] for g in _LABELS) - tp; fn = sum(per[c][p] for p in _LABELS) - tp
        prec = tp / (tp + fp) if (tp + fp) else 0.0; rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1s.append(2 * prec * rec / (prec + rec) if (prec + rec) else 0.0)
    print(f"\n매크로 F1: {sum(f1s)/len(f1s)*100:.1f}%  (불균형 데이터에선 정확도보다 이 지표가 신뢰도 높음)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
