import apiClient from './client';
import type {
  AuthResponse,
  MeResponse,
  RefreshResponse,
  TermsAgreeRequest,
  TermsAgreeResponse,
  KakaoLoginRequest,
  GoogleLoginRequest,
  RefreshRequest,
} from '../types/api';

export const authApi = {
  kakaoLogin: async (req: KakaoLoginRequest): Promise<AuthResponse> => {
    const res = await apiClient.post<{ success: true; data: AuthResponse }>('/auth/kakao', req);
    return res.data.data;
  },

  googleLogin: async (req: GoogleLoginRequest): Promise<AuthResponse> => {
    const res = await apiClient.post<{ success: true; data: AuthResponse }>('/auth/google', req);
    return res.data.data;
  },

  refresh: async (req: RefreshRequest): Promise<RefreshResponse> => {
    const res = await apiClient.post<{ success: true; data: RefreshResponse }>('/auth/refresh', req);
    return res.data.data;
  },

  agree: async (req: TermsAgreeRequest): Promise<TermsAgreeResponse> => {
    const res = await apiClient.post<{ success: true; data: TermsAgreeResponse }>('/auth/agree', req);
    return res.data.data;
  },

  logout: async (): Promise<void> => {
    await apiClient.post('/auth/logout');
  },

  me: async (): Promise<MeResponse> => {
    const res = await apiClient.get<{ success: true; data: MeResponse }>('/auth/me');
    return res.data.data;
  },

  // 개발/테스트 전용 — APP_ENV=development 백엔드에서만 동작
  devLogin: async (): Promise<AuthResponse> => {
    const res = await apiClient.post<{ success: true; data: AuthResponse }>('/auth/dev-login');
    return res.data.data;
  },
};
