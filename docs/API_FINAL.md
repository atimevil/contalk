# 계약똑똑 — 최종 API 명세서 (API Final Specification)

> 작성일: 2026-05-24
> 버전: v1.0-final
> 기준: 실제 구현 코드 (backend/app/api/v1/) 기준
> 초기 계약서(01_design_api-contract.md v1.0, 2026-05-19) 대비 최종 구현 반영본

---

## 전역 규칙

### 기본 URL

```
개발: http://localhost:8000/api/v1
운영: https://api.contalktok.kr/api/v1
```

### 인증 방식

```
모든 인증 필요 엔드포인트:
  Header: Authorization: Bearer {accessToken}

토큰 만료 시:
  accessToken 만료 → 401 응답
  → 프론트엔드에서 POST /auth/refresh 자동 호출
  → 갱신 성공 시 원래 요청 재시도
  → 갱신 실패 시 로그인 화면 리디렉션
```

### 공통 응답 형식

모든 성공 JSON 응답은 `wrap_success_response` 미들웨어에 의해 자동 래핑된다.  
PDF 응답(`/pdf` 경로), 헬스체크(`/health`), 문서 엔드포인트는 래핑 제외.

```typescript
// 성공 응답 (미들웨어 자동 래핑)
interface SuccessResponse<T> {
  success: true;
  data: T;
  meta?: PaginationMeta;
  disclaimer: string;   // AI 면책 고지 (모든 응답에 포함)
}

// 에러 응답
interface ErrorResponse {
  success: false;
  error: {
    code: ErrorCode;
    message: string;        // 사람이 읽을 수 있는 메시지 (한국어)
    details?: unknown;      // 디버깅용 상세 정보 (개발 환경에서만)
    field?: string;         // 폼 유효성 오류 시 해당 필드명
  };
  requestId: string;        // 로그 추적용 UUID (camelCase, BUG-002 NOTE)
  disclaimer: string;
}

// 페이지네이션 메타
interface PaginationMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}
```

> 주의: 전역 에러 핸들러(`RequestValidationError`, 500)는 `requestId`(camelCase)를 사용한다.  
> 개별 엔드포인트 에러(`_error` 함수)는 내부적으로 `request_id`(snake_case)를 사용하지만,  
> `AliasRoute`의 camelCase 직렬화를 통해 `requestId`로 변환된다.

### HTTP 상태 코드 매핑

| 상태 코드 | 의미 |
|---|---|
| 200 | 성공 |
| 201 | 리소스 생성 성공 |
| 202 | 비동기 작업 수락 (분석 요청) |
| 400 | 잘못된 요청 (유효성 오류) |
| 401 | 인증 필요 또는 토큰 만료 |
| 402 | 결제 필요 (할당량 초과 또는 시세 조회 쿼터 소진) |
| 403 | 권한 없음 (다른 사용자 리소스 접근, 프로덕션 전용 기능 차단) |
| 404 | 리소스 없음 |
| 409 | 충돌 (이미 존재하는 리소스) |
| 422 | 처리 불가 엔티티 (OCR 실패 등) |
| 429 | 요청 과도 (Rate Limit) |
| 500 | 서버 내부 오류 |
| 502 | 외부 API 오류 (MOLIT API 오류) |
| 503 | 서비스 일시 중단 (MOLIT API 키 미설정 등) |

### 에러 코드 상수

```typescript
type ErrorCode =
  // 인증
  | 'AUTH_TOKEN_EXPIRED'
  | 'AUTH_TOKEN_INVALID'
  | 'AUTH_REFRESH_EXPIRED'
  | 'AUTH_PROVIDER_FAILED'
  | 'AUTH_TERMS_REQUIRED'

  // 파일 업로드
  | 'FILE_TYPE_INVALID'
  | 'FILE_SIZE_EXCEEDED'
  | 'FILE_UPLOAD_FAILED'

  // OCR / 분석
  | 'OCR_FAILED'
  | 'ANALYSIS_TIMEOUT'
  | 'ANALYSIS_NOT_FOUND'
  | 'ANALYSIS_ALREADY_COMPLETE'

  // 결제
  | 'PAYMENT_PREPARE_FAILED'
  | 'PAYMENT_VERIFY_FAILED'
  | 'PAYMENT_AMOUNT_MISMATCH'
  | 'PAYMENT_ALREADY_USED'

  // 할당량
  | 'QUOTA_EXCEEDED'
  | 'QUOTA_NOT_FOUND'

  // 시세 조회 (신규 추가)
  | 'MARKET_QUOTA_EXCEEDED'     // 무료 시세 조회 3회 소진
  | 'MOLIT_API_ERROR'           // 국토교통부 API 오류
  | 'MARKET_SERVICE_UNAVAILABLE' // MOLIT_API_KEY 미설정 또는 서비스 장애

  // 공통
  | 'VALIDATION_ERROR'
  | 'NOT_FOUND'
  | 'FORBIDDEN'
  | 'INTERNAL_SERVER_ERROR'
  | 'RATE_LIMIT_EXCEEDED';
```

---

## 1. 인증 API (Authentication)

구현 파일: `backend/app/api/v1/auth.py`

### 1.1 카카오 OAuth 로그인

```
POST /auth/kakao
인증 불필요
```

**Request:**
```typescript
interface KakaoLoginRequest {
  code: string;           // 카카오 OAuth 인증 코드
  redirectUri: string;    // OAuth 리디렉션 URI
}
```

**Response (성공 200):**
```typescript
interface AuthResponse {
  accessToken: string;          // JWT, 만료: 1시간
  refreshToken: string;         // JWT, 만료: 30일
  user: UserProfile;
  isNewUser: boolean;           // true이면 약관 동의 필요
}

interface UserProfile {
  id: string;
  email: string;
  nickname?: string;            // Optional (초기 설계: 필수 → 변경)
  profileImageUrl?: string;
  provider: 'kakao' | 'google' | 'email';  // 'email' 추가됨
  createdAt: string;            // ISO 8601
}
```

**에러:**
```
400 VALIDATION_ERROR     — code 누락
401 AUTH_PROVIDER_FAILED — 카카오 서버 오류 또는 코드 만료
```

---

### 1.2 구글 OAuth 로그인

```
POST /auth/google
인증 불필요
```

**Request:**
```typescript
interface GoogleLoginRequest {
  code: string;
  redirectUri: string;
}
```

**Response:** `AuthResponse` (1.1과 동일)

---

### 1.3 토큰 갱신

```
POST /auth/refresh
인증 불필요 (refreshToken 사용)
```

**Request:**
```typescript
interface RefreshRequest {
  refreshToken: string;
}
```

**Response (성공 200):**
```typescript
interface RefreshResponse {
  accessToken: string;
  refreshToken: string;   // 로테이션: 새 refreshToken 발급
}
```

**에러:**
```
401 AUTH_REFRESH_EXPIRED — refreshToken 만료 또는 무효
```

---

### 1.4 약관 동의 저장

```
POST /auth/agree
인증 필요
```

**Request:**
```typescript
interface TermsAgreeRequest {
  termsOfService: boolean;      // 서비스 이용약관 (필수 — true여야 함)
  privacyPolicy: boolean;       // 개인정보 처리방침 (필수 — true여야 함)
  marketing: boolean;           // 마케팅 수신 동의 (선택)
}
```

**Response (성공 200):**
```typescript
interface TermsAgreeResponse {
  agreed: true;
  agreedAt: string;   // ISO 8601
}
```

**에러:**
```
400 VALIDATION_ERROR   — 필수 항목 미동의
401 AUTH_TOKEN_EXPIRED
```

---

### 1.5 로그아웃

```
POST /auth/logout
인증 필요
```

**Request:** 없음

**Response (성공 200):**
```typescript
interface LogoutResponse {
  success: true;
}
```

---

### 1.6 내 프로필 조회

```
GET /auth/me
인증 필요
```

**Response (성공 200):**
```typescript
interface MeResponse {
  user: UserProfile;
  quota: UserQuota;
}

interface UserQuota {
  type: 'none' | 'single' | 'pass_3month';
  remaining: number;          // 잔여 분석 횟수 (-1 = 무제한)
  passExpiresAt?: string;     // 패스 만료일 (패스 구매 시)
}
```

---

### 1.7 개발 환경 전용 로그인 (신규)

```
POST /auth/dev-login
인증 불필요
APP_ENV=development 환경에서만 동작, 프로덕션에서는 403 반환
```

**Request:** 없음 (Body 불필요)

**Response (성공 200):**
```typescript
// SuccessResponse<AuthResponse> 형식으로 래핑됨
interface DevLoginResponse {
  success: true;
  data: AuthResponse;  // 테스트 계정 JWT 토큰 발급
}
```

**동작:**
- 테스트 계정(`dev-test@contalktok.kr`)을 DB에서 찾거나 생성
- 약관 동의 자동 처리
- 단건 이용권 99회 할당
- OAuth 없이 즉시 실제 JWT 발급

**에러:**
```
403 FORBIDDEN — APP_ENV != development (프로덕션 차단)
```

---

## 2. 계약서 분석 API (Analysis)

구현 파일: `backend/app/api/v1/analysis.py`

### 2.1 계약서 업로드 및 분석 시작

```
POST /analysis/upload
인증 필요
Content-Type: multipart/form-data
```

**Request (FormData):**
```typescript
interface UploadRequest {
  file: File;                   // 최대 20MB, JPG/PNG/PDF
  contractType?: 'jeonse'       // 전세
                | 'monthly'     // 월세
                | 'unknown';    // 기본값: 'unknown'
}
```

**Response (성공 202 Accepted):**
```typescript
interface UploadResponse {
  jobId: string;                // 분석 작업 ID (UUID)
  estimatedSeconds: number;     // 예상 소요 시간 (기본: 60)
  status: 'queued';
  disclaimer: string;           // AI 면책 고지 (추가됨)
}
```

**처리 흐름:**
1. 파일 타입 및 크기 검증 (MIME type 기준, 최대 20MB)
2. 할당량 확인 및 차감
3. S3 업로드 (미설정 시 로컬 경로 폴백)
4. Contract 레코드 생성
5. Celery 태스크 디스패치 (`run_analysis_task.delay`)
6. 202 반환 (비동기 처리)

**에러:**
```
400 FILE_TYPE_INVALID      — 지원하지 않는 파일 형식
400 FILE_SIZE_EXCEEDED     — 20MB 초과
401 AUTH_TOKEN_EXPIRED
402 QUOTA_EXCEEDED         — 잔여 횟수 없음 (HTTP 402)
500 FILE_UPLOAD_FAILED     — 스토리지 오류
```

---

### 2.2 분석 상태 조회 (폴링)

```
GET /analysis/{jobId}/status
인증 필요
```

**Response (성공 200):**
```typescript
interface AnalysisStatusResponse {
  jobId: string;
  status: AnalysisStatus;
  progress: number;             // 0–100 (%)
  currentStep: AnalysisStepId;
  completedSteps: AnalysisStepId[];
  reportId?: string;            // status='completed'일 때 설정
  errorCode?: ErrorCode;        // status='failed'일 때 설정
  errorMessage?: string;
}

type AnalysisStatus =
  | 'queued'      // 대기 중
  | 'uploading'   // 업로드 처리 중
  | 'ocr'         // OCR 진행 중
  | 'analyzing'   // AI 분석 중
  | 'generating'  // 특약 생성 중
  | 'completed'   // 완료
  | 'failed';     // 실패

type AnalysisStepId = 'upload' | 'ocr' | 'analyze' | 'clause';
```

**폴링 전략 (프론트엔드):**
```
간격: 2초
최대 시도: 30회 (60초)
완료 시: reportId로 결과 조회
실패 시: errorCode에 따른 에러 처리
타임아웃 시: ANALYSIS_TIMEOUT 처리
```

**에러:**
```
401 AUTH_TOKEN_EXPIRED
403 FORBIDDEN            — 다른 사용자의 jobId 접근
404 ANALYSIS_NOT_FOUND   — 존재하지 않는 jobId
```

---

### 2.3 분석 결과 조회

```
GET /analysis/{reportId}/result
인증 필요
```

**Response (성공 200):**
```typescript
interface AnalysisResultResponse {
  reportId: string;
  jobId: string;
  createdAt: string;
  contractType: 'jeonse' | 'monthly' | 'unknown';

  // 종합 점수
  riskScore: number;            // 0–100 (높을수록 위험)
  riskLevel: 'high' | 'medium' | 'caution' | 'safe';

  // 조항 요약
  summary: {
    high:    number;
    medium:  number;
    caution: number;
    safe:    number;
  };

  // 조항 목록
  clauses: AnalysisClause[];

  // 원문 OCR 텍스트 (선택적 제공)
  ocrText?: string;

  // AI 면책 고지 (신규 추가)
  disclaimer?: string;
}

interface AnalysisClause {
  id: string;
  risk: 'high' | 'medium' | 'caution' | 'safe';
  clauseNumber?: string;        // 예: "제3조"
  originalText: string;         // 계약서 원문
  explanation: string;          // AI 쉬운 설명 (한국어)
  lawReference?: {
    lawName: string;            // 예: "주택임대차보호법"
    article: string;            // 예: "제6조 제1항"
    summary: string;            // 한 줄 요약
    url?: string;               // 국가법령정보센터 링크
  };
  recommendation?: string;      // 수정 권고 사항
  specialClauseDraft?: string;  // AI 생성 특약 초안 (신규)
}
```

> 주의: AI 파이프라인이 `"normal"`로 반환한 위험도는 `contract_service.py`에서 `"safe"`로 자동 정규화된다.

**에러:**
```
401 AUTH_TOKEN_EXPIRED
403 FORBIDDEN
404 ANALYSIS_NOT_FOUND
```

---

### 2.4 결과 PDF 다운로드

```
GET /analysis/{reportId}/pdf
인증 필요
```

**Response (성공 200):**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="contract_analysis_{reportId}.pdf"
[PDF 바이너리 — ReportLab 생성]
```

**구현 상태:** 엔드포인트 존재, `pdf_service.generate_analysis_pdf()` 호출  
**주의:** `pdf_service` 구현 완성도에 따라 실제 PDF 품질이 다를 수 있음

**에러:**
```
401 AUTH_TOKEN_EXPIRED
403 FORBIDDEN
404 ANALYSIS_NOT_FOUND
```

---

### 2.5 특약사항 추천 목록 조회

```
GET /analysis/{reportId}/special-clauses
인증 필요
```

**Response (성공 200):**
```typescript
interface SpecialClausesResponse {
  reportId: string;
  clauses: SpecialClause[];
  disclaimer: string;
}

interface SpecialClause {
  id: string;
  relatedRiskClauseId: string;    // 연관된 위험 조항 ID
  relatedRisk: 'high' | 'medium' | 'caution';
  title: string;                  // 예: "제3조 관련 특약"
  text: string;                   // 추천 특약 문구
  category: SpecialClauseCategory;
  isEditable: boolean;            // 항상 true
}

type SpecialClauseCategory =
  | 'renewal'         // 갱신 관련
  | 'repair'          // 수선비 관련
  | 'deposit'         // 보증금 반환
  | 'entry'           // 전입신고/확정일자
  | 'termination'     // 계약 해지
  | 'facility'        // 시설물
  | 'other';          // 기타
```

**특약 문구 우선순위:**
1. AI 생성 특약 초안 (`special_clause_draft`)
2. AI 파이프라인 `special_texts` 목록
3. `recommendation` 필드 값
4. 사용자 수정 이력 (`SpecialClauseEdit` 테이블)

**에러:**
```
401 AUTH_TOKEN_EXPIRED
403 FORBIDDEN
404 ANALYSIS_NOT_FOUND
```

---

### 2.6 특약 초안 PDF 다운로드

```
GET /analysis/{reportId}/special-clauses/pdf
인증 필요
```

**Response (성공 200):**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="special_clauses_{reportId}.pdf"
[PDF 바이너리 — ReportLab 생성]
```

**구현 상태:** 엔드포인트 존재, `pdf_service.generate_special_clauses_pdf()` 호출

---

### 2.7 특약 문구 사용자 수정 저장

```
PATCH /analysis/{reportId}/special-clauses/{clauseId}
인증 필요
```

**Request:**
```typescript
interface UpdateSpecialClauseRequest {
  text: string;         // 수정된 문구 (최대 2000자)
}
```

**Response (성공 200):**
```typescript
interface UpdateSpecialClauseResponse {
  id: string;
  text: string;
  updatedAt: string;    // ISO 8601
  disclaimer: string;
}
```

---

### 2.8 분석 이력 목록

```
GET /analysis/history
인증 필요
Query: ?page=1&perPage=10
```

**Response (성공 200):**
```typescript
interface AnalysisHistoryResponse {
  analyses: AnalysisHistoryItem[];
  meta: {
    total: number;
    page: number;
    per_page: number;
    total_pages: number;
  };
}

interface AnalysisHistoryItem {
  reportId: string;
  createdAt: string;
  contractType: 'jeonse' | 'monthly' | 'unknown';
  riskScore: number;
  riskLevel: 'high' | 'medium' | 'caution' | 'safe';
  summary: {
    high: number;
    medium: number;
    caution: number;
    safe: number;
  };
}
```

---

### 2.9 잔여 할당량 조회

```
GET /user/quota
인증 필요
```

**Response (성공 200):**
```typescript
interface UserQuota {
  type: 'none' | 'single' | 'pass_3month';
  remaining: number;
  passExpiresAt?: string;       // ISO 8601
}
```

---

## 3. 결제 API (Payment)

구현 파일: `backend/app/api/v1/payments.py`

> 포트원(iamport) v1 REST API 연동 기준  
> (초기 계획: v2 → 실제 구현: v1 REST API로 변경됨)

### 3.1 결제 준비

```
POST /payment/prepare
인증 필요
```

**Request:**
```typescript
interface PaymentPrepareRequest {
  plan: 'single' | 'pass_3month';
}
```

**Response (성공 200):**
```typescript
interface PaymentPrepareResponse {
  merchantUid: string;          // 고유 주문번호 (포트원에 전달)
  amount: number;               // 결제 금액 (원, 환경변수 PRICE_SINGLE/PRICE_PASS_3MONTH)
  plan: 'single' | 'pass_3month';
  planLabel: string;            // 예: "건당 이용권"
  pgProvider: string;           // 환경변수 PORTONE_PG_PROVIDER (기본: html5_inicis)
}
```

**에러:**
```
400 VALIDATION_ERROR
401 AUTH_TOKEN_EXPIRED
```

---

### 3.2 결제 검증

```
POST /payment/verify
인증 필요
```

**Request:**
```typescript
interface PaymentVerifyRequest {
  impUid: string;               // 포트원 결제 고유번호
  merchantUid: string;          // 3.1에서 발급한 주문번호
}
```

**Response (성공 200):**
```typescript
interface PaymentVerifyResponse {
  success: true;
  paymentId: string;
  plan: 'single' | 'pass_3month';
  amount: number;
  paidAt: string;               // ISO 8601
  quota: UserQuota;             // 갱신된 할당량
}
```

**에러:**
```
400 PAYMENT_AMOUNT_MISMATCH  — 결제 금액 불일치
400 PAYMENT_ALREADY_USED     — 이미 검증된 impUid
401 AUTH_TOKEN_EXPIRED
500 PAYMENT_VERIFY_FAILED    — 포트원 서버 오류
```

---

### 3.3 결제 이력 조회

```
GET /payment/history
인증 필요
Query: ?page=1&perPage=10
```

**Response (성공 200):**
```typescript
interface PaymentHistoryResponse {
  payments: PaymentRecord[];
  meta?: PaginationMeta;        // 페이지네이션 메타 포함
}

interface PaymentRecord {
  id: string;
  plan: 'single' | 'pass_3month';
  planLabel: string;
  amount: number;
  status: 'paid' | 'cancelled' | 'failed';
  paidAt: string;
  expiresAt?: string;           // 패스 만료일
}
```

---

### 3.4 포트원 웹훅 수신 (서버-서버)

```
POST /payment/webhook
인증 불필요 (포트원 IP 화이트리스트 검증)
```

**Request (포트원 전송):**
```typescript
interface PortOneWebhookBody {
  imp_uid: string;
  merchant_uid: string;
  status: 'paid' | 'cancelled' | 'failed';
}
```

**Response (성공 200):** `{ received: true }`

---

## 4. 시세 조회 API (Market) — 신규

구현 파일: `backend/app/api/v1/market.py`  
외부 의존: 국토교통부(MOLIT) 실거래가 API  
API 승인 현황:
- 매매 실거래가: 2026-05-06 ~ 2028-05-06 승인 완료
- 전월세 실거래가: 2026-05-23 ~ 2028-05-23 승인 완료

### 4.1 시도·시군구 코드 목록

```
GET /market/districts
인증 불필요
```

**Response (성공 200):**
```typescript
interface DistrictsResponse {
  items: SidoItem[];
}

interface SidoItem {
  name: string;     // 예: "서울특별시"
  code: string;     // 예: "11"
  시군구: DistrictItem[];
}

interface DistrictItem {
  name: string;     // 예: "강남구"
  code: string;     // 예: "11680" (법정동코드 5자리)
}
```

**특징:** 정적 데이터 반환 (MOLIT API 호출 없음)

---

### 4.2 법정동 목록

```
GET /market/dongs
인증 불필요
```

**Query Parameters:**
```
district_code  string  필수  법정동코드 5자리 (예: 11680)
deal_ym        string  선택  조회 연월 YYYYMM (기본: 직전 달)
```

**Response (성공 200):**
```typescript
interface DongsResponse {
  district_code: string;
  deal_ym: string;
  dongs: string[];          // 법정동 이름 목록
}
```

**에러:**
```
400 VALIDATION_ERROR             — district_code 형식 오류 또는 deal_ym 형식 오류
503 MARKET_SERVICE_UNAVAILABLE   — MOLIT_API_KEY 미설정
```

---

### 4.3 아파트 매매 실거래가 통계

```
GET /market/apt-trade
인증 불필요
```

**Query Parameters:**
```
district_code  string   필수  법정동코드 5자리 (예: 11680 = 서울 강남구)
deal_ym        string   선택  조회 연월 YYYYMM (기본: 직전 달)
area_min       float    선택  최소 전용면적 필터 (㎡)
area_max       float    선택  최대 전용면적 필터 (㎡)
```

**Response (성공 200):**
```typescript
interface AptTradeStat {
  district_code: string;
  district_name?: string;
  deal_ym: string;
  count: number;            // 거래 건수
  avg_price_krw: number;    // 평균 매매가 (원)
  min_price_krw: number;    // 최저 매매가 (원)
  max_price_krw: number;    // 최고 매매가 (원)
  items: AptTradeItem[];    // 개별 거래 내역
}

interface AptTradeItem {
  apartment: string;        // 단지명
  area: number;             // 전용면적 (㎡)
  price_krw: number;        // 거래가 (원)
  floor?: string;           // 층
  deal_date: string;        // 거래일 (YYYY-MM-DD)
}
```

**에러:**
```
400 VALIDATION_ERROR             — 파라미터 형식 오류
502 MOLIT_API_ERROR              — MOLIT API 오류 응답
503 MARKET_SERVICE_UNAVAILABLE   — MOLIT_API_KEY 미설정 또는 서비스 장애
```

---

### 4.4 아파트 전세 실거래가 통계

```
GET /market/apt-rent
인증 불필요
```

**Query Parameters:** `/market/apt-trade`와 동일

**Response (성공 200):**
```typescript
interface AptRentStat {
  district_code: string;
  district_name?: string;
  deal_ym: string;
  count: number;
  avg_deposit_krw: number;    // 평균 전세 보증금 (원)
  min_deposit_krw: number;    // 최저 전세 보증금 (원)
  max_deposit_krw: number;    // 최고 전세 보증금 (원)
  items: AptRentItem[];
}

interface AptRentItem {
  apartment: string;
  area: number;
  deposit_krw: number;        // 보증금 (원)
  monthly_rent_krw: number;   // 월세 (원, 전세인 경우 0)
  is_jeonse: boolean;         // 전세 여부
  floor?: string;
  deal_date: string;
}
```

**주의:** 전세 API 미승인 상태에서는 `rent=null` 반환 (매매 데이터만 응답)

**에러:** `/market/apt-trade`와 동일

---

### 4.5 매매+전세 통합 시세 요약 (전세가율 계산)

```
GET /market/summary
인증 필요
무료 3회 제공 후 이용권 구매 필요
```

**Query Parameters:**
```
district_code  string   필수  법정동코드 5자리
deal_ym        string   선택  조회 연월 YYYYMM
area_min       float    선택  최소 전용면적 (㎡)
area_max       float    선택  최대 전용면적 (㎡)
dong           string   선택  법정동 이름 필터 (예: 역삼동). 미지정 시 시군구 전체 평균
```

**Response (성공 200):**
```typescript
interface MarketSummaryResponse {
  district_code: string;
  district_name: string | null;
  deal_ym: string;
  trade: {
    count: number;
    avg_price_krw: number;
    min_price_krw: number;
    max_price_krw: number;
  };
  rent: {
    count: number;
    avg_deposit_krw: number;
    min_deposit_krw: number;
    max_deposit_krw: number;
  } | null;                         // 전세 API 미승인 시 null
  jeonse_ratio_pct: number | null;  // 전세가율 (%) = avg_deposit / avg_price * 100
  market_queries_remaining: number; // 남은 무료 조회 횟수
  market_queries_limit: number;     // 무료 조회 한도 (현재: 3회)
  disclaimer: string;
}
```

**쿼터 정책:**
- 사용자당 무료 3회 제공 (`User.market_queries_used` DB 컬럼)
- MOLIT API 호출 성공 시에만 차감 (실패 시 차감 없음)
- 한도 초과 시 HTTP 402 반환

**에러:**
```
400 VALIDATION_ERROR             — 파라미터 형식 오류
401 AUTH_TOKEN_EXPIRED
402 MARKET_QUOTA_EXCEEDED        — 무료 조회 3회 소진
502 MOLIT_API_ERROR              — MOLIT API 오류
503 MARKET_SERVICE_UNAVAILABLE   — MOLIT_API_KEY 미설정
```

---

## 5. 기타 API

### 5.1 헬스체크

```
GET /health
인증 불필요
```

**Response (성공 200):**
```typescript
interface HealthResponse {
  status: 'ok';
  version: string;
  timestamp: string;
  disclaimer: string;
}
```

```
GET /api/v1/health  (동일 응답)
```

---

## 6. Rate Limit 정책

```
비로그인:  분당 10회 (IP 기준)
로그인:    분당 60회 (사용자 기준)
업로드:    시간당 10회 (사용자 기준)
결제:      분당 5회 (사용자 기준)

초과 시: HTTP 429 + Retry-After 헤더 (초 단위)
구현: slowapi 기반 Rate Limiting 미들웨어
```

---

## 7. API 통신 공통 헤더

```
Request Headers:
  Content-Type: application/json (JSON 요청 시)
  Authorization: Bearer {accessToken} (인증 필요 시)
  X-Client-Version: 1.0.0 (앱 버전)
  X-Request-Id: {UUID} (프론트에서 생성, 로그 추적용)

Response Headers:
  Content-Type: application/json
  X-Request-Id: {동일 UUID 반환}
  X-RateLimit-Remaining: {잔여 요청 수}
  X-RateLimit-Reset: {리셋 시각 Unix timestamp}
```

---

## 8. camelCase 직렬화 정책

백엔드는 Pydantic `snake_case` 필드를 `AliasRoute` + `CamelModel` 조합으로 프론트엔드에 `camelCase`로 변환하여 응답한다.

```
구현: backend/app/main.py → default_route_class=AliasRoute
      backend/app/schemas/common.py → CamelModel (alias_generator=to_camel)
      모든 스키마: CamelModel 상속
```

**예시:**
```
백엔드 스키마 필드    →    API 응답 키
job_id               →    jobId
report_id            →    reportId
created_at           →    createdAt
is_new_user          →    isNewUser
```

---

## 9. 환경변수 목록

### 백엔드 환경변수

```bash
# 앱 기본
APP_ENV=development          # development | production
APP_VERSION=1.0.0

# 데이터베이스
DATABASE_URL=postgresql+asyncpg://...
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# JWT
SECRET_KEY=...               # 최소 32자, 프로덕션에서 반드시 변경
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30

# AWS S3 (미설정 시 로컬 파일 경로 폴백)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-northeast-2
S3_BUCKET_NAME=contalktok-contracts

# AI
OPENAI_API_KEY=              # GPT-4o Vision OCR + RAG 법령 근거 생성
OPENAI_MODEL=gpt-5.4
KLUE_ROBERTA_MODEL_PATH=foxibu/contalk-risk-classifier

# 벡터 DB (ChromaDB)
CHROMA_HOST=chromadb
CHROMA_PORT=8001
CHROMA_COLLECTION_NAME=lease_law

# 소셜 로그인
KAKAO_CLIENT_ID=
KAKAO_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# 공공 API
LAW_API_KEY=                 # 법제처 생활법령정보 API (ChromaDB 색인용)
MOLIT_API_KEY=               # 국토교통부 실거래가 API (시세 조회용)

# 포트원 결제 (v1 REST API)
PORTONE_IMP_KEY=
PORTONE_IMP_SECRET=
PORTONE_PG_PROVIDER=html5_inicis
PORTONE_WEBHOOK_SECRET=

# 가격 설정 (원 단위)
PRICE_SINGLE=5000
PRICE_PASS_3MONTH=19900

# CORS
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://contalktok.kr
```

### 프론트엔드 환경변수 (Vite)

```bash
VITE_API_URL=http://localhost:8000
VITE_ENABLE_MOCK=true        # MSW 목업 활성화 여부
VITE_PORTONE_IMP_CODE=imp_xxxxxxxx
VITE_KAKAO_APP_KEY=...
VITE_GOOGLE_CLIENT_ID=...
```
