"""
GPT 기반 조항 재라벨링 (시범/전체).

기존 rule-based 라벨(data/train.jsonl)의 "caution 강제 상향" 편향을 벗어나기 위해,
조항 텍스트를 GPT로 3-class(medium/caution/safe) 재분류한다.
high(전세사기/깡통전세)는 classifier의 규칙 레이어가 별도 처리하므로 GPT는 3-class만 판단한다.

사용 (docker):
  # 시범 100개 — 기존 라벨과 분포·일치율 비교
  docker compose run --rm --no-deps -w /work -v <root>:/work backend \
    python scripts/relabel_with_gpt.py --n 100

  # 전체 재라벨링 → data/train.gpt.jsonl 저장
  docker compose run ... backend python scripts/relabel_with_gpt.py --all --out data/train.gpt.jsonl

비용: 조항당 1회 호출. 시범 100개는 소액. 전체는 입력 토큰 규모만큼.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backend"))


def _load_dotenv():
    """host 직접 실행 시 프로젝트 루트 .env에서 환경변수 로드 (docker는 env_file로 주입)."""
    env_path = os.path.join(_ROOT, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


_load_dotenv()

_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4")
_TRAIN = os.path.join(_ROOT, "data", "train.jsonl")

_SYSTEM = """당신은 한국 주택임대차 계약서 조항의 위험도를 분류하는 전문가입니다.
임차인 관점에서 각 조항을 다음 3개 등급 중 하나로 분류하세요.

핵심 원칙: 임대차 계약에는 임차인의 의무·제약이 당연히 포함됩니다.
의무가 존재한다는 이유만으로 위험으로 보지 마세요. **표준 계약서에 통상적으로 들어가는
조항은 safe**이며, 그 통상적 범위를 **명백히 넘어 과도하거나 일방적으로 불리할 때만**
등급을 올립니다.

- safe: 표준적·통상적 조항. 임차인 의무가 있어도 일반적 범위면 safe.
  (예: 보증금·차임 지급 절차, 임대차 기간, 상호 협의 조정, 임대인의 사용·수익 보장,
   통상적인 수선 책임 분담, 일반적인 원상복구 의무, 관리비 납부, 전세 보증금 무이자,
   퇴거 후 보증금 반환 등 — 표준 계약서에 흔히 있는 조항)
- caution: 생활상 제약이나 경미한 불이익.
  (예: 전대 금지, 반려동물·흡연 금지, 시설·인테리어 변경 제한)
- medium: 표준 범위를 넘어 임차인에게 명백히 과도·일방적으로 불리하거나 분쟁 소지가 큰 조항.
  (예: 수선·원상복구 비용을 임차인에게 전부/부당하게 전가, 사유 없는 보증금 무단 공제,
   보증금 반환 거절·지연, 임대인의 일방적 해지권, 과도한 위약금·연체이자,
   사전 통보 없는 임의 방문, 단전·단수 등 자력집행)

판단 기준:
- "수선/원상복구/관리비/보증금 무이자" 등은 그 자체로는 **safe**입니다.
  '전부', '일체', '무조건', '부당하게', '사유 없이' 처럼 과도·일방성이 명시될 때만 medium으로 올리세요.
- "불리한 계약서에 들어있다"는 이유로 평범한 조항을 올리지 마세요. 조항 내용만으로 판단합니다.
- 애매하면 더 낮은 등급(safe)을 선택하세요.
- 전세사기/깡통전세 같은 치명 위험은 별도 규칙이 처리하므로 여기서는 고려하지 않습니다.

반드시 아래 JSON 형식으로만 답하세요. 다른 설명은 출력하지 마세요.
{"label": "safe|caution|medium", "reason": "한 줄 근거"}"""


def _make_client():
    from openai import OpenAI  # type: ignore

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("OPENAI_API_KEY 미설정 — 중단", file=sys.stderr)
        sys.exit(1)
    return OpenAI(api_key=api_key)


def _label_one(client, text: str) -> dict:
    """단일 조항 GPT 분류. 실패 시 {'label': None}."""
    try:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": text[:1500]},
            ],
        )
        raw = resp.choices[0].message.content.strip()
        # JSON 추출 (코드펜스 등 제거)
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            raw = raw[start : end + 1]
        data = json.loads(raw)
        label = data.get("label", "").strip().lower()
        if label not in ("safe", "caution", "medium"):
            return {"label": None, "reason": f"잘못된 라벨: {label}"}
        return {"label": label, "reason": data.get("reason", "")}
    except Exception as exc:  # noqa: BLE001
        return {"label": None, "reason": f"오류: {exc}"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100, help="시범 라벨링 샘플 수")
    parser.add_argument("--balanced", action="store_true", help="기존 라벨별 균등 샘플")
    parser.add_argument("--all", action="store_true", help="전체 재라벨링")
    parser.add_argument("--src", default="", help="입력 jsonl 경로 (기본: data/train.jsonl)")
    parser.add_argument("--out", default="", help="전체 모드 출력 jsonl 경로")
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()

    src = os.path.join(_ROOT, args.src) if args.src else _TRAIN
    with open(src, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]

    if args.all:
        pass
    elif args.balanced:
        random.seed()  # 매 실행 랜덤 샘플 (시드 고정 안 함)
        by_label = collections.defaultdict(list)
        for r in rows:
            by_label[r["label"]].append(r)
        per = max(1, args.n // len(by_label))
        sel = []
        for lab, items in by_label.items():
            random.shuffle(items)
            sel.extend(items[:per])
        rows = sel
    else:
        rows = rows[: args.n]

    client = _make_client()
    print(f"모델: {_MODEL} | 대상: {len(rows)}개 조항 | workers: {args.workers}")

    results = [None] * len(rows)

    def _task(i_row):
        i, row = i_row
        out = _label_one(client, row["text"])
        return i, out

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(_task, (i, r)): i for i, r in enumerate(rows)}
        done = 0
        for fut in as_completed(futures):
            i, out = fut.result()
            results[i] = out
            done += 1
            if done % 25 == 0:
                print(f"  진행 {done}/{len(rows)}")

    # ── 분포 + 기존 라벨 대비 비교 ──────────────────────────────────────────────
    gpt_dist = collections.Counter()
    rule_dist = collections.Counter()
    agree = total = fail = 0
    changes = collections.Counter()

    for row, res in zip(rows, results):
        g = res["label"]
        r = row["label"]
        rule_dist[r] += 1
        if g is None:
            fail += 1
            continue
        gpt_dist[g] += 1
        total += 1
        if g == r:
            agree += 1
        else:
            changes[f"{r}→{g}"] += 1

    print("\n" + "=" * 70)
    print(f"GPT 재라벨링 결과 ({len(rows)}개, 실패 {fail})")
    print("=" * 70)
    print(f"기존(rule) 분포: {dict(rule_dist)}")
    print(f"GPT 분포:        {dict(gpt_dist)}")
    if total:
        print(f"일치율: {agree}/{total} ({agree/total*100:.0f}%)")
    print(f"주요 변경: {dict(changes.most_common(8))}")

    # 변경 샘플 근거 출력 (검증용) — safe/caution → medium 위주
    if not args.all:
        print("\n--- 변경 샘플 근거 (rule→GPT) ---")
        shown = 0
        for row, res in zip(rows, results):
            g, r = res["label"], row["label"]
            if g and g != r and ("medium" in (g, r)) and shown < 10:
                print(f"[{r}→{g}] {res.get('reason', '')[:70]}")
                print(f"    조항: {row['text'][:100].strip().replace(chr(10), ' ')}")
                shown += 1

    if args.all and args.out:
        out_path = os.path.join(_ROOT, args.out)
        with open(out_path, "w", encoding="utf-8") as f:
            label2id = {"safe": 0, "caution": 1, "medium": 2}
            for row, res in zip(rows, results):
                g = res["label"] or row["label"]  # 실패 시 기존 라벨 유지
                f.write(json.dumps(
                    {"text": row["text"], "label": g, "label_id": label2id[g]},
                    ensure_ascii=False,
                ) + "\n")
        print(f"\n저장: {args.out}")


if __name__ == "__main__":
    main()
