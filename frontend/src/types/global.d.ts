/**
 * 외부 SDK 글로벌 타입 선언
 */

// 카카오 JavaScript SDK
interface KakaoAuth {
  authorize(options: {
    redirectUri: string;
    scope?: string;
    state?: string;
  }): void;
}

interface KakaoStatic {
  init(appKey: string): void;
  isInitialized(): boolean;
  Auth: KakaoAuth;
}

// 포트원(아임포트) SDK
interface IMPRequestPayParams {
  pg: string;
  pay_method: string;
  merchant_uid: string;
  name: string;
  amount: number;
  buyer_email?: string;
  buyer_name?: string;
  buyer_tel?: string;
  m_redirect_url?: string;
}

interface IMPResponse {
  success: boolean;
  imp_uid: string;
  merchant_uid: string;
  error_msg?: string;
  error_code?: string;
}

interface IMPStatic {
  init(impCode: string): void;
  request_pay(
    params: IMPRequestPayParams,
    callback: (response: IMPResponse) => void
  ): void;
}

declare global {
  interface Window {
    Kakao?: KakaoStatic;
    IMP?: IMPStatic;
  }
}

export {};
