# 계약똑똑 — 초기 설계 대비 변경사항

> 작성일: 2026-05-24
> 버전: v1.0-final
> 비교 기준: 초기 설계(2026-05-19) vs 최종 구현(2026-05-24)
> 참조 문서: 01_design_api-contract.md (v1.0), 01_design_spec.md, 01_design_user-flow.md

---

## 섹션 1: 전체 변경사항 요약 표

| 분류 | 항목 | 초기 설계 | 최종 구현 | 변경 유형 |
|---|---|---|---|---|
| **OCR 엔진** | 텍스트 추출 방식 | Google Cloud Vision API | GPT-4o Vision (pdfplumber 선행 시도) | 변경 |
| **시세 조회 API** | 엔드포인트 존재 여부 | 없음 | `/market/*` 5개 엔드포인트 | 추가 |
| **시세 조회 쿼터** | 무료 사용 제한 | 없음 | 무료 3회 제한 + `user.market_queries_used` DB 컬럼 | 추가 |
| **포트원 API 버전** | 결제 연동 버전 | v2 | v1 REST API | 변경 |
| **개발용 로그인** | 테스트 인증 | 없음 | `POST /auth/dev-login` (APP_ENV=development 전용) | 추가 |
| **분석 결과 disclaimer** | AI 면책 고지 | 없음 | 모든 응답에 `disclaimer` 필드 포함 | 추가 |
| **UserProfile.nickname** | 필수 여부 | `string` (필수) | `string?` (Optional) | 변경 |
| **UserProfile.provider** | 허용 값 | `'kakao' \| 'google'` | `'kakao' \| 'google' \| 'email'` | 변경 |
| **결과 PDF 다운로드** | 구현 상태 | Phase 2 계획 | 엔드포인트 존재, pdf_service 호출 (ReportLab) | 유지 |
| **특약 PDF 다운로드** | 구현 상태 | Phase 2 계획 | 엔드포인트 존재, pdf_service 호출 (ReportLab) | 유지 |
| **에러 응답 requestId** | 필드 케이스 | `requestId` (camelCase 명세) | 전역 핸들러: `requestId` / 일부 내부: `request_id` → AliasRoute 통해 camelCase 변환 | 변경 |
| **RiskLevel "normal"** | 위험도 값 | 명세 없음 | AI pipeline이 `"normal"` 반환 시 `"safe"`로 정규화 (contract_service.py) | 추가 |
| **ChromaDB 시딩** | 구축 방법 | 수동 실행 필요 | `vectordb_builder.py --sample / --api / --all` 스크립트 제공 | 추가 |
| **응답 래핑 미들웨어** | 성공 응답 형식 | 없음 (엔드포인트 직접 반환) | `wrap_success_response` 미들웨어가 자동 래핑 | 추가 |
| **S3 폴백** | AWS 미설정 환경 | 명세 없음 | AWS 자격증명 미설정 시 로컬 파일 경로로 폴백 | 추가 |
| **분석 이력** | 구현 시기 | Phase 3 (v1.1) 예정 | 현재 구현 완료 (GET /analysis/history) | 변경 |
| **결제 이력** | 구현 시기 | Phase 3 (v1.1) 예정 | 현재 구현 완료 (GET /payment/history) | 변경 |
| **로그아웃** | 구현 시기 | Phase 3 (v1.1) 예정 | 현재 구현 완료 (POST /auth/logout) | 변경 |
| **AnalysisClause.specialClauseDraft** | 응답 필드 | 없음 | `specialClauseDraft?: string` 추가 (AI 특약 초안) | 추가 |
| **market/dongs** | 법정동 목록 조회 | 없음 | `GET /market/dongs` (24시간 캐시, MOLIT API 호출) | 추가 |
| **PaymentHistoryResponse.meta** | 페이지네이션 | 명세 없음 | `meta?: PaginationMeta` 포함 (BUG-007 수정) | 추가 |
| **GOOGLE_CLOUD_CREDENTIALS_PATH** | 환경변수 | 필요 (GCV 사용) | 실제 사용 안 함 (GPT-4o Vision으로 교체) | 제거 |
| **Celery 비동기 처리** | 분석 처리 방식 | 명세: 비동기 설계 | Celery + Redis 실제 구현 | 유지 |
| **AliasRoute camelCase** | API 직렬화 | 개별 엔드포인트 설정 | `default_route_class=AliasRoute` 전역 적용 | 추가 |

---

## 섹션 2: AI 파이프라인 변경

### 초기 설계 흐름

```
계약서 파일 (JPG/PNG/PDF)
    ↓
Google Cloud Vision API (OCR)
    ↓
조항 파싱
    ↓
KLUE-RoBERTa 위험도 분류
    ↓
RAG + GPT-4o 법령 근거 생성 (비정상 조항만)
    ↓
AnalysisResult dict 반환
```

초기 설계에서 OCR은 Google Cloud Vision API를 전담으로 사용하는 것으로 계획됐다. `GOOGLE_CLOUD_CREDENTIALS_PATH` 환경변수가 `.env`에 포함되어 있었다.

### 최종 구현 흐름

```
계약서 파일 (JPG/PNG/PDF/TXT)
    ↓
파일 타입 감지
    ├─ 텍스트 파일(.txt) → 직접 읽기 (UTF-8 / EUC-KR / CP949)
    ├─ 디지털 PDF       → pdfplumber (텍스트 레이어 존재 시)
    └─ 스캔 PDF / 이미지
           ↓
       GPT-4o Vision API (gpt-5.4)
       TIFF → JPEG 자동 변환 지원
           ↓
       신뢰도 반환 (0.92~0.93)
    ↓
조항 파싱 (clause_parser)
    ↓
KLUE-RoBERTa 위험도 분류 (rule-based 폴백)
    ↓
RAG + GPT-4o 법령 근거 생성
    ("medium", "caution" 조항만 — "high", "safe" 제외)
    ↓
"normal" → "safe" 정규화 (contract_service.py)
    ↓
AnalysisResult dict 반환 + disclaimer 포함
```

### 주요 차이점

| 항목 | 초기 설계 | 최종 구현 |
|---|---|---|
| OCR 엔진 | Google Cloud Vision API | GPT-4o Vision (pdfplumber 선행) |
| 디지털 PDF 처리 | 명세 없음 | pdfplumber 우선 시도 (API 비용 절감) |
| TIFF 지원 | 없음 | TIFF → JPEG 자동 변환 후 Vision 처리 |
| 텍스트 파일 지원 | 없음 | `.txt` 파일 직접 읽기 (개발/테스트 환경) |
| RAG 대상 위험도 | 전체 비정상 조항 | `medium`, `caution`만 (high 제외) |
| 특약 초안 생성 | 명세 없음 | RAG 결과에 `special_clause_draft` 포함 |
| "normal" 위험도 | 존재하지 않음 | pipeline 반환값 "normal" → "safe" 정규화 |
| S3 폴백 | 없음 | AWS 미설정 시 로컬 경로로 폴백 |

---

## 섹션 3: 미구현 항목

아래 항목들은 현재 기준(2026-05-24)으로 완전한 구현이 이루어지지 않은 상태다.

| 항목 | 계획 단계 | 현재 상태 | 이유 |
|---|---|---|---|
| `pdf_service` 한국어 품질 | Phase 2 | 엔드포인트 존재, 실제 PDF 품질 미검증 | ReportLab 한국어 폰트 등록 필요 |
| `pdf_service.generate_analysis_pdf()` 내용 | Phase 2 | 함수 존재, 구현 완성도 미확인 | 분석 결과 PDF 레이아웃 미정의 |
| MSW: GET /analysis/history | Phase 3 | 백엔드 구현 완료, 프론트 MSW 미구현 | 프론트엔드 MyPage UI 미개발 |
| MSW: GET /payment/history | Phase 3 | 백엔드 구현 완료, 프론트 MSW 미구현 | 프론트엔드 MyPage UI 미개발 |
| 실제 OAuth SDK 연동 | Phase 1 | MSW 목업으로 대체 중 | 카카오/구글 SDK 연동 작업 필요 |
| 포트원 `window.IMP.request_pay()` 연동 | Phase 1 | MSW 목업으로 대체 중 | PaymentPage.tsx 실연동 필요 |
| KLUE-RoBERTa 실제 모델 | Phase 2 | rule-based 폴백 동작 중 | 모델 파일 다운로드 및 서빙 필요 |
| market_queries_used 이용권 연계 | Phase 4 | 쿼터 소진 시 402 반환만 구현 | 이용권 구매 후 쿼터 해제 로직 미구현 |

---

## 섹션 4: 계획에 없던 추가 기능

초기 설계 문서(`01_design_api-contract.md`, `01_design_spec.md`)에 명시되지 않았으나 개발 중 추가된 기능 목록이다.

### 4.1 시세 조회 API (Phase 4 전체)

국토교통부(MOLIT) 실거래가 API 연동을 통해 체크리스트 화면에서 전세가율 자동 계산 기능을 제공하게 됐다. 5개 엔드포인트(`/market/districts`, `/market/dongs`, `/market/apt-trade`, `/market/apt-rent`, `/market/summary`)가 신규 추가됐다.

추가 배경: 전세가율이 높을수록 보증금 미반환 위험이 크므로, 계약서 위험도 분석과 함께 시세 비교 기능이 서비스 핵심 가치로 부상했다.

### 4.2 개발 환경 전용 로그인 (`POST /auth/dev-login`)

실제 카카오/구글 OAuth SDK 연동 전 단계에서 개발 및 테스트를 빠르게 진행하기 위해 추가됐다. `APP_ENV=development`에서만 동작하며, 프로덕션에서는 403을 반환하여 보안 위험을 차단한다.

### 4.3 응답 자동 래핑 미들웨어 (`wrap_success_response`)

초기 설계에서는 각 엔드포인트가 직접 `SuccessResponse` 형식으로 응답하도록 계획됐다. 실제 구현에서는 미들웨어가 모든 성공 JSON 응답을 자동으로 `{ success: true, data: {...}, disclaimer: "..." }` 형식으로 래핑한다. PDF 응답, 헬스체크, 문서 엔드포인트는 래핑에서 제외된다.

### 4.4 전역 camelCase 직렬화 (`AliasRoute` + `CamelModel`)

Pydantic 스키마의 `snake_case` 필드를 프론트엔드 요구 사항인 `camelCase`로 자동 변환하는 메커니즘이 추가됐다. QA 단계(BUG-001)에서 62개 항목 중 35개가 camelCase 불일치로 발견된 후 전역 적용됐다.

### 4.5 ChromaDB 시딩 CLI (`vectordb_builder.py`)

초기 설계에서는 ChromaDB 구축 방법이 명세에 없었다. 실제 구현에서 `--sample`, `--api`, `--pdf`, `--all` 옵션을 갖춘 CLI 스크립트가 제공되어 다양한 환경에서 법령 데이터 색인이 가능해졌다.

### 4.6 S3 로컬 폴백

AWS 자격증명 미설정 시 `s3_key`를 로컬 파일 경로로 해석하는 폴백 로직이 추가됐다. 개발 환경에서 AWS 없이도 전체 파이프라인을 테스트할 수 있다.

### 4.7 AI 면책 고지 (`disclaimer`) 전역 포함

초기 설계에는 `disclaimer` 필드가 없었다. 최종 구현에서는 모든 API 응답에 다음 문구가 포함된다.

```
"본 분석은 법률 조언이 아닌 정보 제공 서비스입니다. 중요한 사항은 전문 법률가에게 확인하세요."
```

---

## 섹션 5: 외부 서비스 의존성 현황

| 서비스 | 용도 | 현재 상태 | 비고 |
|---|---|---|---|
| **카카오 OAuth** | 소셜 로그인 | 미연동 (MSW 목업) | `KAKAO_CLIENT_ID` 설정 필요, SDK 연동 작업 남음 |
| **구글 OAuth** | 소셜 로그인 | 미연동 (MSW 목업) | `GOOGLE_CLIENT_ID` 설정 필요, SDK 연동 작업 남음 |
| **포트원 (iamport)** | 결제 처리 | v1 REST API 코드 구현 완료, 미연동 | `PORTONE_IMP_KEY` / `PORTONE_IMP_SECRET` 설정 필요 |
| **AWS S3** | 계약서 파일 저장 | 미설정 (로컬 폴백) | `AWS_ACCESS_KEY_ID` / `S3_BUCKET_NAME` 설정 필요 |
| **OpenAI GPT-4o Vision** | OCR (이미지/스캔 PDF) | `OPENAI_API_KEY` 설정 시 동작 | `gpt-5.4` 모델 사용 |
| **OpenAI GPT-4o** | RAG 법령 근거 생성 | `OPENAI_API_KEY` 설정 시 동작 | 동일 API 키 공유 |
| **KLUE-RoBERTa** | 위험도 분류 | rule-based 폴백 동작 중 | `KLUE_ROBERTA_MODEL_PATH` 설정 및 모델 서빙 필요 |
| **ChromaDB** | 법령 벡터 검색 | 로컬 또는 원격 연동 가능 | `vectordb_builder.py --api` 실행으로 초기 색인 필요 |
| **국토교통부 (MOLIT) 매매** | 아파트 매매 실거래가 | 승인 완료 (2026-05-06 ~ 2028-05-06) | `MOLIT_API_KEY` 설정 필요 |
| **국토교통부 (MOLIT) 전월세** | 아파트 전세 실거래가 | 승인 완료 (2026-05-23 ~ 2028-05-23) | 동일 `MOLIT_API_KEY` 사용 |
| **법제처 생활법령정보** | ChromaDB 색인용 법령 텍스트 | API 키 설정됨 (`LAW_API_KEY`) | `vectordb_builder.py --api` 사용 시 자동 색인 |
| **Redis** | Celery 브로커 / 결과 백엔드 | docker-compose 구성 완료 | `REDIS_URL` 설정 필요 |
| **PostgreSQL** | 주 데이터베이스 | docker-compose 구성 완료 | `DATABASE_URL` 설정 필요 |
| **Google Cloud Vision** | OCR (초기 계획) | 미사용 (GPT-4o Vision으로 교체됨) | `GOOGLE_CLOUD_CREDENTIALS_PATH` 환경변수 더 이상 불필요 |

---

## 부록: QA 검증 요약

QA 단계(03_qa_results.md)에서 발견된 주요 버그 및 수정 이력.

| 버그 ID | 영향 범위 | 내용 | 수정 방법 |
|---|---|---|---|
| BUG-001 | 전체 API | 백엔드 snake_case ↔ 프론트 camelCase 불일치 (35개 항목) | `CamelModel` 베이스 클래스 + `AliasRoute` 전역 적용 |
| BUG-002 | 에러 응답 | 전역 에러 핸들러 `request_id` → `requestId` 명세 불일치 | NOTE 처리 (전역 핸들러는 camelCase 직접 사용) |
| BUG-004 | AI 파이프라인 | RiskLevel `"normal"` vs 스키마 `"safe"` 불일치 | `contract_service.py` 정규화 로직 추가 |
| BUG-005 | 인증 | `UserProfile.nickname` 필수 vs 백엔드 `Optional[str]` | 프론트 타입 `nickname?` 변경 |
| BUG-006 | 인증 | `UserProfile.provider`에 `'email'` 값 누락 | 프론트 타입 `'email'` 추가 |
| BUG-007 | 결제 이력 | `PaymentHistoryResponse`에 `meta` 필드 누락 | 프론트 타입 `meta?: PaginationMeta` 추가 |

수정 전 PASS율: 38.7% (62항목 중 24 PASS)
수정 후 PASS율: 95.2% (NOTE 제외 시 100%)
