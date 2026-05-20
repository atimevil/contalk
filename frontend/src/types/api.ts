// ============================================================
// 공통 응답 타입
// ============================================================

export interface SuccessResponse<T> {
  success: true;
  data: T;
  meta?: PaginationMeta;
}

export interface ErrorResponse {
  success: false;
  error: {
    code: ErrorCode;
    message: string;
    details?: unknown;
    field?: string;
  };
  requestId: string;
}

export interface PaginationMeta {
  total: number;
  page: number;
  perPage: number;
  totalPages: number;
}

export type ErrorCode =
  | 'AUTH_TOKEN_EXPIRED'
  | 'AUTH_TOKEN_INVALID'
  | 'AUTH_REFRESH_EXPIRED'
  | 'AUTH_PROVIDER_FAILED'
  | 'AUTH_TERMS_REQUIRED'
  | 'FILE_TYPE_INVALID'
  | 'FILE_SIZE_EXCEEDED'
  | 'FILE_UPLOAD_FAILED'
  | 'OCR_FAILED'
  | 'ANALYSIS_TIMEOUT'
  | 'ANALYSIS_NOT_FOUND'
  | 'ANALYSIS_ALREADY_COMPLETE'
  | 'PAYMENT_PREPARE_FAILED'
  | 'PAYMENT_VERIFY_FAILED'
  | 'PAYMENT_AMOUNT_MISMATCH'
  | 'PAYMENT_ALREADY_USED'
  | 'QUOTA_EXCEEDED'
  | 'QUOTA_NOT_FOUND'
  | 'VALIDATION_ERROR'
  | 'NOT_FOUND'
  | 'FORBIDDEN'
  | 'INTERNAL_SERVER_ERROR'
  | 'RATE_LIMIT_EXCEEDED';

// ============================================================
// 인증 타입
// ============================================================

export interface UserProfile {
  id: string;
  email: string;
  nickname?: string;            // BUG-005 fix: 백엔드 Optional[str] 반영
  profileImageUrl?: string;
  provider: 'kakao' | 'google' | 'email';  // BUG-006 fix: 백엔드 "email" provider 추가
  createdAt: string;
}

export interface UserQuota {
  type: 'none' | 'single' | 'pass_3month';
  remaining: number;
  passExpiresAt?: string;
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  user: UserProfile;
  isNewUser: boolean;
}

export interface RefreshResponse {
  accessToken: string;
  refreshToken: string;
}

export interface MeResponse {
  user: UserProfile;
  quota: UserQuota;
}

export interface TermsAgreeRequest {
  termsOfService: boolean;
  privacyPolicy: boolean;
  marketing: boolean;
}

export interface TermsAgreeResponse {
  agreed: true;
  agreedAt: string;
}

export interface KakaoLoginRequest {
  code: string;
  redirectUri: string;
}

export interface GoogleLoginRequest {
  code: string;
  redirectUri: string;
}

export interface RefreshRequest {
  refreshToken: string;
}

// ============================================================
// 분석 타입
// ============================================================

export interface UploadResponse {
  jobId: string;
  estimatedSeconds: number;
  status: 'queued';
}

export type AnalysisStatus =
  | 'queued'
  | 'uploading'
  | 'ocr'
  | 'analyzing'
  | 'generating'
  | 'completed'
  | 'failed';

export type AnalysisStepId = 'upload' | 'ocr' | 'analyze' | 'clause';

export interface AnalysisStatusResponse {
  jobId: string;
  status: AnalysisStatus;
  progress: number;
  currentStep: AnalysisStepId;
  completedSteps: AnalysisStepId[];
  reportId?: string;
  errorCode?: ErrorCode;
  errorMessage?: string;
}

export type RiskLevel = 'high' | 'medium' | 'caution' | 'safe';

export interface LawReference {
  lawName: string;
  article: string;
  summary: string;
  url?: string;
}

export interface AnalysisClause {
  id: string;
  risk: RiskLevel;
  clauseNumber?: string;
  originalText: string;
  explanation: string;
  lawReference?: LawReference;
  recommendation?: string;
}

export interface AnalysisResultResponse {
  reportId: string;
  jobId: string;
  createdAt: string;
  contractType: 'jeonse' | 'monthly' | 'unknown';
  riskScore: number;
  riskLevel: RiskLevel;
  summary: {
    high: number;
    medium: number;
    caution: number;
    safe: number;
  };
  clauses: AnalysisClause[];
  ocrText?: string;
}

export interface QuotaResponse {
  type: 'none' | 'single' | 'pass_3month';
  remaining: number;
  passExpiresAt?: string;
}

// ============================================================
// 특약사항 타입
// ============================================================

export type SpecialClauseCategory =
  | 'renewal'
  | 'repair'
  | 'deposit'
  | 'entry'
  | 'termination'
  | 'facility'
  | 'other';

export interface SpecialClause {
  id: string;
  relatedRiskClauseId: string;
  relatedRisk: 'high' | 'medium' | 'caution';
  title: string;
  text: string;
  category: SpecialClauseCategory;
  isEditable: boolean;
}

export interface SpecialClausesResponse {
  reportId: string;
  clauses: SpecialClause[];
}

export interface UpdateSpecialClauseRequest {
  text: string;
}

export interface UpdateSpecialClauseResponse {
  id: string;
  text: string;
  updatedAt: string;
}

// ============================================================
// 결제 타입
// ============================================================

export type PaymentPlan = 'single' | 'pass_3month';

export interface PaymentPrepareRequest {
  plan: PaymentPlan;
}

export interface PaymentPrepareResponse {
  merchantUid: string;
  amount: number;
  plan: PaymentPlan;
  planLabel: string;
  pgProvider: string;
}

export interface PaymentVerifyRequest {
  impUid: string;
  merchantUid: string;
}

export interface PaymentVerifyResponse {
  success: true;
  paymentId: string;
  plan: PaymentPlan;
  amount: number;
  paidAt: string;
  quota: UserQuota;
}

export interface PaymentRecord {
  id: string;
  plan: PaymentPlan;
  planLabel: string;
  amount: number;
  status: 'paid' | 'cancelled' | 'failed';
  paidAt: string;
  expiresAt?: string;
}

export interface PaymentHistoryResponse {
  payments: PaymentRecord[];
  meta?: PaginationMeta;        // BUG-007 fix: 백엔드 PaymentHistoryResponse에 meta 포함
}
