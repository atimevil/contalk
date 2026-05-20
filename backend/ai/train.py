"""
KLUE-RoBERTa 파인튜닝 스크립트

klue/roberta-base 모델을 임대차 계약서 위험도 3-class 분류 태스크로 파인튜닝한다.

클래스:
    0: safe    — 정상 조항
    1: caution — 주의 조항
    2: medium  — 위험 조항

실행 방법:
    python -m backend.ai.train
    python -m backend.ai.train --epochs 5 --batch-size 16
    python -m backend.ai.train --output-dir models/roberta_v1

환경변수:
    KLUE_ROBERTA_MODEL_PATH — 완료 후 분류기에서 사용할 저장 경로

요구사항:
    transformers>=4.30, torch>=2.0, scikit-learn
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _PROJECT_ROOT / "data"
_DEFAULT_OUTPUT_DIR = _PROJECT_ROOT / "models" / "roberta_risk_classifier"

_LABEL2ID = {"safe": 0, "caution": 1, "medium": 2}
_ID2LABEL = {v: k for k, v in _LABEL2ID.items()}
_BASE_MODEL = "klue/roberta-base"


# ---------------------------------------------------------------------------
# 데이터 로딩
# ---------------------------------------------------------------------------

def load_jsonl(path: Path) -> List[dict]:
    """JSONL 파일을 로드한다."""
    samples = []
    with open(str(path), encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


# ---------------------------------------------------------------------------
# 파인튜닝
# ---------------------------------------------------------------------------

def train(
    train_path: Path,
    val_path: Path,
    output_dir: Path,
    base_model: str = _BASE_MODEL,
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    max_length: int = 256,
    warmup_ratio: float = 0.1,
    use_class_weights: bool = True,
) -> None:
    """
    KLUE-RoBERTa 모델을 파인튜닝한다.

    Parameters
    ----------
    use_class_weights : bool
        True이면 클래스 불균형 보정을 위해 가중치 손실 사용
    """
    try:
        import torch
        from torch import nn
        from transformers import (
            AutoTokenizer,
            AutoModelForSequenceClassification,
            TrainingArguments,
            Trainer,
            EarlyStoppingCallback,
        )
        from datasets import Dataset  # type: ignore
        import numpy as np
        from sklearn.metrics import classification_report  # type: ignore
    except ImportError as exc:
        logger.error(
            "필요 패키지 미설치: %s\n"
            "pip install transformers torch datasets scikit-learn",
            exc,
        )
        raise

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("학습 장치: %s", device)

    # ── 데이터 로딩 ──────────────────────────────────────────────────────────
    logger.info("훈련 데이터 로드: %s", train_path)
    train_data = load_jsonl(train_path)
    val_data = load_jsonl(val_path)
    logger.info("훈련: %d개, 검증: %d개", len(train_data), len(val_data))

    # ── 레이블 분포 확인 ─────────────────────────────────────────────────────
    from collections import Counter
    train_label_counts = Counter(s["label"] for s in train_data)
    logger.info("훈련 레이블 분포: %s", dict(train_label_counts))

    # ── 클래스 가중치 계산 (불균형 보정) ────────────────────────────────────
    class_weights = None
    if use_class_weights:
        import numpy as np
        from sklearn.utils.class_weight import compute_class_weight  # type: ignore

        labels = [s["label_id"] for s in train_data]
        present_classes = sorted(set(labels))

        if len(present_classes) < len(_LABEL2ID):
            missing = set(_LABEL2ID.values()) - set(present_classes)
            logger.warning("훈련 데이터에 없는 클래스: %s", {_ID2LABEL[m] for m in missing})

        weights = compute_class_weight(
            "balanced",
            classes=np.array(present_classes),
            y=np.array(labels),
        )
        # 전체 3클래스 weight 배열 구성 (없는 클래스는 1.0)
        all_weights = [1.0] * len(_LABEL2ID)
        for cls_id, w in zip(present_classes, weights):
            all_weights[cls_id] = float(w)

        class_weights = torch.tensor(all_weights, dtype=torch.float)
        logger.info("클래스 가중치: %s", {_ID2LABEL[i]: round(w, 2) for i, w in enumerate(all_weights)})

    # ── 토크나이저 + 데이터셋 ────────────────────────────────────────────────
    logger.info("토크나이저 로드: %s", base_model)
    tokenizer = AutoTokenizer.from_pretrained(base_model)

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            padding="max_length",
            max_length=max_length,
        )

    train_ds = Dataset.from_list([{"text": s["text"], "labels": s["label_id"]} for s in train_data])
    val_ds = Dataset.from_list([{"text": s["text"], "labels": s["label_id"]} for s in val_data])

    train_ds = train_ds.map(tokenize, batched=True, remove_columns=["text"])
    val_ds = val_ds.map(tokenize, batched=True, remove_columns=["text"])
    train_ds.set_format("torch")
    val_ds.set_format("torch")

    # ── 모델 ─────────────────────────────────────────────────────────────────
    logger.info("모델 로드: %s", base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=len(_LABEL2ID),
        id2label=_ID2LABEL,
        label2id=_LABEL2ID,
    )
    model.to(device)

    # ── 커스텀 Trainer (클래스 가중치 손실) ─────────────────────────────────
    class WeightedTrainer(Trainer):
        def __init__(self, *args, class_weights=None, **kwargs):
            super().__init__(*args, **kwargs)
            self._class_weights = class_weights

        def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
            labels = inputs.pop("labels")
            outputs = model(**inputs)
            logits = outputs.logits

            if self._class_weights is not None:
                loss_fn = nn.CrossEntropyLoss(weight=self._class_weights.to(logits.device))
            else:
                loss_fn = nn.CrossEntropyLoss()

            loss = loss_fn(logits, labels)
            return (loss, outputs) if return_outputs else loss

    # ── 평가 지표 ─────────────────────────────────────────────────────────────
    def compute_metrics(eval_pred):
        logits, labels = eval_pred
        preds = logits.argmax(axis=-1)

        present = sorted(set(labels.tolist()))
        target_names = [_ID2LABEL[i] for i in present]
        report = classification_report(
            labels, preds,
            labels=present,
            target_names=target_names,
            output_dict=True,
            zero_division=0,
        )

        return {
            "accuracy": report["accuracy"],
            "f1_macro": report["macro avg"]["f1-score"],
            "f1_weighted": report["weighted avg"]["f1-score"],
        }

    # ── 학습 설정 ─────────────────────────────────────────────────────────────
    output_dir.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size * 2,
        learning_rate=learning_rate,
        warmup_steps=int(7471 / batch_size * warmup_ratio),
        weight_decay=0.01,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="f1_weighted",
        greater_is_better=True,
        logging_steps=50,
        fp16=torch.cuda.is_available(),
        report_to="none",
        seed=42,
    )

    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
        class_weights=class_weights,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    # ── 학습 시작 ─────────────────────────────────────────────────────────────
    logger.info("파인튜닝 시작 — epochs=%d, batch=%d, lr=%s", epochs, batch_size, learning_rate)
    trainer.train()

    # ── 최종 평가 ─────────────────────────────────────────────────────────────
    eval_results = trainer.evaluate()
    logger.info("최종 검증 결과: %s", eval_results)

    # ── 모델 저장 ─────────────────────────────────────────────────────────────
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    results_path = output_dir / "eval_results.json"
    results_path.write_text(json.dumps(eval_results, indent=2), encoding="utf-8")

    logger.info("모델 저장 완료: %s", output_dir)
    logger.info(
        "사용 방법: 환경변수 KLUE_ROBERTA_MODEL_PATH=%s 설정 후 서버 재시작",
        output_dir,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    parser = argparse.ArgumentParser(description="KLUE-RoBERTa 위험도 분류기 파인튜닝")
    parser.add_argument("--train-path", type=str, default=str(_DATA_DIR / "train.jsonl"))
    parser.add_argument("--val-path", type=str, default=str(_DATA_DIR / "val.jsonl"))
    parser.add_argument("--output-dir", type=str, default=str(_DEFAULT_OUTPUT_DIR))
    parser.add_argument("--base-model", type=str, default=_BASE_MODEL)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--no-class-weights", action="store_true")
    args = parser.parse_args()

    train_path = Path(args.train_path)
    val_path = Path(args.val_path)

    if not train_path.exists():
        logger.error("훈련 데이터 없음: %s\npython -m backend.ai.data_prep 먼저 실행하세요.", train_path)
        return

    train(
        train_path=train_path,
        val_path=val_path,
        output_dir=Path(args.output_dir),
        base_model=args.base_model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_length=args.max_length,
        use_class_weights=not args.no_class_weights,
    )


if __name__ == "__main__":
    main()
