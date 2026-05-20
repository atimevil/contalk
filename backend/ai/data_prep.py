"""
KLUE-RoBERTa 파인튜닝용 훈련 데이터 추출 스크립트

데이터 소스:
    019.법률, 규정 (판결서, 약관 등) 텍스트 분석 데이터/
        01.데이터/1.Training/...TS_2.약관/01.유리/  → safe 레이블
        01.데이터/1.Training/...TS_2.약관/02.불리/  → rule-based 분류 레이블
        01.데이터/2.Validation/...VS_2.약관/01.유리/ → safe 레이블
        01.데이터/2.Validation/...VS_2.약관/02.불리/ → rule-based 분류 레이블

실행 방법:
    python -m backend.ai.data_prep
    python -m backend.ai.data_prep --limit 100    # 파일 수 제한 (테스트용)
    python -m backend.ai.data_prep --contract-only  # 임대차 계약만

출력:
    data/train.jsonl  — 훈련 데이터
    data/val.jsonl    — 검증 데이터
    data/stats.json   — 데이터셋 통계
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterator, List, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 데이터셋 경로 설정
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATASET_ROOT = _PROJECT_ROOT / "019.법률, 규정 (판결서, 약관 등) 텍스트 분석 데이터" / "01.데이터"

_TRAINING_DIRS = [
    (_DATASET_ROOT / "1.Training/원천데이터_230510_add/TS_2.약관/TS_2.약관/1.Training/원천데이터/TS_2.약관/01.유리", "safe"),
    (_DATASET_ROOT / "1.Training/원천데이터_230510_add/TS_2.약관/TS_2.약관/1.Training/원천데이터/TS_2.약관/02.불리", "risky"),
]

_VALIDATION_DIRS = [
    (_DATASET_ROOT / "2.Validation/원천데이터_230510_add/VS_2.약관/VS_2.약관/2.Validation/원천데이터/VS_2.약관/01.유리", "safe"),
    (_DATASET_ROOT / "2.Validation/원천데이터_230510_add/VS_2.약관/VS_2.약관/2.Validation/원천데이터/VS_2.약관/02.불리", "risky"),
]

_OUTPUT_DIR = _PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# XML 파싱
# ---------------------------------------------------------------------------

def _extract_text_from_xml(xml_path: Path) -> str:
    """XML 파일의 <cn> CDATA에서 계약서 원문을 추출한다."""
    try:
        tree = ET.parse(str(xml_path))
        root = tree.getroot()
        cn_elem = root.find(".//cn")
        if cn_elem is not None and cn_elem.text:
            return cn_elem.text.strip()
    except ET.ParseError as exc:
        logger.warning("XML 파싱 실패 (%s): %s", xml_path.name, exc)
    return ""


def _iter_xml_files(
    directories: List[Tuple[Path, str]],
    contract_only: bool = True,
    limit: int = 0,
) -> Iterator[Tuple[str, str, Path]]:
    """
    디렉토리에서 XML 파일을 순회하며 (raw_text, folder_label, path)를 반환한다.

    Parameters
    ----------
    contract_only : bool
        True이면 임대차 계약 파일만 처리
    limit : int
        디렉토리당 최대 파일 수 (0=제한없음)
    """
    for dir_path, folder_label in directories:
        if not dir_path.exists():
            logger.warning("디렉토리 없음: %s", dir_path)
            continue

        xml_files = sorted(dir_path.glob("*.xml"))
        if contract_only:
            xml_files = [f for f in xml_files if "임대차" in f.name]

        dir_count = 0
        for xml_file in xml_files:
            if limit and dir_count >= limit:
                break
            raw_text = _extract_text_from_xml(xml_file)
            if raw_text:
                yield raw_text, folder_label, xml_file
                dir_count += 1


# ---------------------------------------------------------------------------
# 조항 파싱 + 레이블 부여
# ---------------------------------------------------------------------------

def _label_clause(clause_text: str, folder_label: str) -> str:
    """
    조항 텍스트에 훈련 레이블을 부여한다.

    전략:
    - 유리(safe) 폴더: 모든 조항 → safe
    - 불리(risky) 폴더: rule-based 분류기로 세분화
      high/medium/caution 이면 해당 레이블
      rule-based에서 safe로 나오면 caution으로 상향 (문서 레벨 신호 반영)
    """
    if folder_label == "safe":
        return "safe"

    from .classifier import _classify_with_rules
    risk = _classify_with_rules(clause_text)

    if risk == "safe":
        return "caution"
    return risk


def _process_contract(raw_text: str, folder_label: str) -> List[dict]:
    """
    계약서 원문 텍스트를 조항 단위로 분해하고 레이블을 부여한다.

    Returns
    -------
    List[dict]
        [{"text": str, "label": str}, ...]
    """
    from .clause_parser import parse_clauses

    clauses = parse_clauses(raw_text)
    if not clauses:
        return []

    samples = []
    for clause in clauses:
        text = clause.get("text", "").strip()
        if len(text) < 10:  # 너무 짧은 조항 제외
            continue

        label = _label_clause(text, folder_label)
        samples.append({
            "text": text[:512],  # RoBERTa max input 고려
            "label": label,
        })

    return samples


# ---------------------------------------------------------------------------
# 데이터셋 빌드
# ---------------------------------------------------------------------------

_LABEL2ID = {"safe": 0, "caution": 1, "medium": 2, "high": 3}


def build_dataset(
    contract_only: bool = True,
    limit: int = 0,
    val_ratio: float = 0.15,
) -> dict:
    """
    XML 파일을 읽어 훈련/검증 JSONL로 저장한다.

    Returns
    -------
    dict
        통계 정보
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    train_samples: List[dict] = []
    val_samples: List[dict] = []
    stats = {"train": {}, "val": {}, "files_processed": 0, "files_skipped": 0}

    # 훈련 데이터 추출
    logger.info("훈련 데이터 추출 중...")
    for raw_text, folder_label, xml_path in _iter_xml_files(_TRAINING_DIRS, contract_only, limit):
        samples = _process_contract(raw_text, folder_label)
        if samples:
            train_samples.extend(samples)
            stats["files_processed"] += 1
            logger.debug("처리: %s → %d개 조항", xml_path.name, len(samples))
        else:
            stats["files_skipped"] += 1

    # 검증 데이터 추출
    logger.info("검증 데이터 추출 중...")
    for raw_text, folder_label, xml_path in _iter_xml_files(_VALIDATION_DIRS, contract_only, limit):
        samples = _process_contract(raw_text, folder_label)
        if samples:
            val_samples.extend(samples)
            stats["files_processed"] += 1
        else:
            stats["files_skipped"] += 1

    # 검증 세트에 누락된 레이블이 있으면 훈련 데이터에서 보충
    train_labels = {s["label"] for s in train_samples}
    val_labels = {s["label"] for s in val_samples}
    missing_in_val = train_labels - val_labels

    if missing_in_val:
        logger.info("검증 세트 누락 레이블: %s — 훈련 데이터에서 보충", missing_in_val)
        import random
        random.seed(42)
        extra_val: List[dict] = []
        remaining_train: List[dict] = []
        for label in missing_in_val:
            class_samples = [s for s in train_samples if s["label"] == label]
            n_take = max(1, int(len(class_samples) * val_ratio))
            random.shuffle(class_samples)
            extra_val.extend(class_samples[:n_take])
            # 훈련에서 제거한 샘플 추적
            taken_ids = set(id(s) for s in class_samples[:n_take])
            remaining_train.extend(s for s in train_samples if id(s) not in taken_ids)
        train_samples = remaining_train
        val_samples.extend(extra_val)
        random.shuffle(val_samples)

    # 레이블 분포 계산
    stats["train"] = _count_labels(train_samples)
    stats["val"] = _count_labels(val_samples)
    stats["train_total"] = len(train_samples)
    stats["val_total"] = len(val_samples)

    # JSONL 저장
    _write_jsonl(_OUTPUT_DIR / "train.jsonl", train_samples)
    _write_jsonl(_OUTPUT_DIR / "val.jsonl", val_samples)

    # 통계 저장
    stats_path = _OUTPUT_DIR / "stats.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    return stats


def _count_labels(samples: List[dict]) -> dict:
    counts: dict = {}
    for s in samples:
        label = s["label"]
        counts[label] = counts.get(label, 0) + 1
    return counts


def _write_jsonl(path: Path, samples: List[dict]) -> None:
    with open(str(path), "w", encoding="utf-8") as f:
        for sample in samples:
            record = {
                "text": sample["text"],
                "label": sample["label"],
                "label_id": _LABEL2ID.get(sample["label"], 0),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    logger.info("%s 저장 완료: %d개 샘플", path.name, len(samples))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="KLUE-RoBERTa 훈련 데이터 추출")
    parser.add_argument("--contract-only", action="store_true", default=True,
                        help="임대차 계약 파일만 처리 (기본: True)")
    parser.add_argument("--all-contracts", action="store_true",
                        help="모든 계약 유형 처리 (--contract-only 해제)")
    parser.add_argument("--limit", type=int, default=0,
                        help="처리할 최대 XML 파일 수 (0=제한없음)")
    args = parser.parse_args()

    contract_only = not args.all_contracts

    logger.info("데이터셋 추출 시작 (임대차만=%s, 파일제한=%d)", contract_only, args.limit)
    stats = build_dataset(contract_only=contract_only, limit=args.limit)

    print("\n===== 데이터셋 추출 완료 =====")
    print(f"처리된 파일: {stats['files_processed']}개")
    print(f"스킵된 파일: {stats['files_skipped']}개")
    print(f"\n훈련 세트: {stats['train_total']}개 조항")
    for label, cnt in sorted(stats['train'].items()):
        pct = cnt / stats['train_total'] * 100 if stats['train_total'] else 0
        print(f"  {label:8s}: {cnt:4d}개 ({pct:.1f}%)")
    print(f"\n검증 세트: {stats['val_total']}개 조항")
    for label, cnt in sorted(stats['val'].items()):
        pct = cnt / stats['val_total'] * 100 if stats['val_total'] else 0
        print(f"  {label:8s}: {cnt:4d}개 ({pct:.1f}%)")
    print(f"\n저장 위치: {_OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
