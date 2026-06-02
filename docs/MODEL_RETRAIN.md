# 위험도 분류 모델 재학습 가이드

KLUE-RoBERTa 위험도 분류기(3-class)를 **GPT 재라벨링 데이터**로 재학습하는 절차다.
GPU 환경에서 이 문서만 보고 따라 하면 된다.

---

## 1. 배경 — 왜 재학습하는가

기존 학습 데이터(`data/train.jsonl`)는 **rule-based로 자동 라벨링**되어 두 가지 문제가 있었다.

| 문제 | 내용 |
|------|------|
| **caution 85% 편향** | `data_prep.py`가 "불리 폴더의 평범한 조항"을 전부 caution으로 강제 상향 |
| **safe 라벨 부정확** | "유리 폴더 → 전부 safe"로 뭉뚱그려, 단전·단수 같은 명백한 위험조차 safe |
| **medium 6%뿐** | 모델이 medium을 거의 학습 못 함 (예측 확률 ~0.003) |

→ 측정 결과 위험 등급 분류 정확도 **33%**, 전세사기/깡통전세 미탐.

이를 해결하기 위해 **조항을 GPT로 임차인 관점에서 재라벨링**했다 (`scripts/relabel_with_gpt.py`).

### 라벨 분포 비교

| 클래스 | 기존(rule) | **GPT 재라벨** |
|--------|-----------|---------------|
| safe    | 8.7%  | **23.0%** |
| caution | 85.1% | **10.6%** |
| medium  | 6.2%  | **66.4%** |

medium이 10배 늘어 모델이 위험 조항을 학습할 수 있게 됐고, caution 편향이 해소됐다.
medium 66%는 원본이 "불리 약관" 위주인 데이터 특성이며, 학습 시 **class weight**로 보정한다.

> 참고: high(전세사기·깡통전세 등 치명 위험)는 모델 클래스가 아니라 `classifier.py`의
> 규칙 레이어(`_CRITICAL_PATTERNS`)로 별도 부여한다. 모델은 3-class만 학습한다.

---

## 2. 전체 흐름

```
git clone → 의존성 설치 → 재학습 → 모델 업로드(HF Hub) → 서비스 .env 변경 → 효과 측정
```

학습 데이터(`data/train.gpt.jsonl`, `val.gpt.jsonl`)는 **이미 repo에 포함**되어 있으므로
재라벨링을 다시 할 필요는 없다.

---

## 3. GPU 환경 준비

```bash
git clone https://github.com/atimevil/contalk.git
cd contalk

# 학습 의존성 설치 (repo에는 포함 안 됨)
pip install -r backend/requirements-train.txt
#   또는 최소: pip install "transformers>=4.30" "torch>=2.0" datasets scikit-learn
```

- **GPU/CUDA 드라이버**가 있어야 빠르다. CPU로도 동작하지만 매우 느리다.
- 학습에는 **OpenAI API 키가 필요 없다** (이미 라벨링된 데이터로 학습만 함).

### 데이터 확인

```bash
wc -l data/train.gpt.jsonl data/val.gpt.jsonl
# 7471 train / 1355 val
```

---

## 4. 재학습 실행

```bash
python -m backend.ai.train \
  --train-path data/train.gpt.jsonl \
  --val-path   data/val.gpt.jsonl \
  --output-dir models/roberta_gpt_v1
```

### 주요 옵션 (기본값)

| 옵션 | 기본 | 설명 |
|------|------|------|
| `--epochs` | 3 | 학습 epoch 수 |
| `--batch-size` | 16 | 배치 크기 (GPU 메모리 따라 조정) |
| `--learning-rate` | 2e-5 | 학습률 |
| `--max-length` | 256 | 토큰 최대 길이 |
| `--base-model` | klue/roberta-base | 베이스 모델 |
| `--no-class-weights` | (꺼짐) | 지정 시 class weight 비활성화 (권장하지 않음) |

- **class weight는 기본 활성화** — medium 66% 불균형을 자동 보정한다.
- EarlyStopping(patience=2) + `f1_weighted` 기준 best model 자동 선택.

### 학습 산출물

```
models/roberta_gpt_v1/
├── config.json, model.safetensors, tokenizer 파일들
└── eval_results.json   ← 최종 검증 지표 (accuracy, f1_macro, f1_weighted)
```

---

## 5. 학습된 모델 가져오기

모델(~400–500MB)은 git으로 관리하지 않는다(`models/`는 gitignore). 두 방법 중 택일.

### 방법 A — HuggingFace Hub (권장, 현재 방식과 동일)

**GPU 환경에서 업로드:**
```bash
pip install huggingface_hub
huggingface-cli login          # write 권한 토큰 입력
huggingface-cli upload <계정>/contalk-risk-classifier-v2 models/roberta_gpt_v1 .
```

**서비스 환경에서 적용 — `.env` 한 줄만 변경:**
```bash
KLUE_ROBERTA_MODEL_PATH=<계정>/contalk-risk-classifier-v2
```
서비스 재시작 시 자동 다운로드된다. private repo면 서비스 환경에 `HF_TOKEN`도 설정.

### 방법 B — 직접 파일 복사

```bash
# GPU → 서비스 서버
scp -r user@gpu-host:/path/contalk/models/roberta_gpt_v1 ./models/
```
```bash
# .env
KLUE_ROBERTA_MODEL_PATH=models/roberta_gpt_v1
```

---

## 6. 효과 측정

`measure_ai_quality.py`는 app 의존(pydantic/sqlalchemy) 없이 독립 실행되므로,
**재학습 직후 같은 GPU 환경에서 바로** 측정할 수 있다.

```bash
pip install pdfplumber          # PDF 텍스트 추출용 (학습 의존성 외 추가 1개)

KLUE_ROBERTA_MODEL_PATH=models/roberta_gpt_v1 \
  python scripts/measure_ai_quality.py
```

또는 서비스(docker) 환경에서:
```bash
docker compose run --rm --no-deps -w /work -v "<repo경로>:/work" \
  backend python scripts/measure_ai_quality.py
```

- **OpenAI 호출 없음** (pdfplumber로 PDF 텍스트 추출 + 로컬 모델 분류).
- 측정 항목: 계약 유형 감지 정확도 / 위험 등급 분류 정확도 (재학습 전 33% → 개선 기대).
- 테스트 계약서: `tests/contracts/contract_*.pdf` (파일명에 정답 라벨 포함).

> 정리: **재학습(4) → 측정(6)** 까지 GPU 환경 한 곳에서 끝낼 수 있다.
> 필요한 추가 설치는 측정용 `pdfplumber` 하나뿐이다.

---

## 7. (참고) 데이터를 다시 재라벨링하려면

원본 rule 데이터를 새로 GPT 재라벨링할 경우:

```bash
# 1) 원천데이터 → rule 라벨
python -m backend.ai.data_prep

# 2) GPT 재라벨링 (임차인 관점 3-class). OPENAI_API_KEY 필요 (.env 자동 로드)
python scripts/relabel_with_gpt.py --all \
  --src data/train.jsonl --out data/train.gpt.jsonl --workers 24
python scripts/relabel_with_gpt.py --all \
  --src data/val.jsonl --out data/val.gpt.jsonl --workers 24
```

- `--balanced --n 150` : 라벨별 균등 시범 (전체 전 품질 확인용)
- `--workers` : 동시 호출 수 (rate limit 시 낮춤). 실패분은 기존 라벨 유지.

---

## 8. 트러블슈팅

| 증상 | 원인 / 해결 |
|------|------------|
| `PermissionError ... /root/.cache/huggingface` | HF 캐시 권한 — docker는 이미 `data/hf_cache` bind mount로 수정됨. host는 `HF_HOME`을 쓰기 가능 경로로 |
| 학습이 너무 느림 | GPU 미사용(CPU). CUDA 드라이버 확인 (`torch.cuda.is_available()`) |
| `transformers 미설치` | `pip install -r backend/requirements-train.txt` |
| medium만 과다 예측 | class weight 켜졌는지 확인 (`--no-class-weights` 안 줬는지), epochs 조정 |

---

## 관련 파일

| 파일 | 역할 |
|------|------|
| `backend/ai/train.py` | KLUE-RoBERTa 파인튜닝 (class weight 내장) |
| `backend/ai/classifier.py` | 추론 — 모델 3-class + 규칙 high 승격 |
| `scripts/relabel_with_gpt.py` | GPT 재라벨링 도구 |
| `scripts/measure_ai_quality.py` | 분류 품질 측정 |
| `backend/ai/data_prep.py` | 원천데이터 → rule 라벨 (재라벨링 전 단계) |
| `data/train.gpt.jsonl`, `val.gpt.jsonl` | GPT 재라벨 학습셋 (repo 포함) |
