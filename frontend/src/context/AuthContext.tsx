import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { UserProfile, UserQuota } from '../types/api';
import { authApi } from '../api/auth';

interface AuthState {
  isLoggedIn: boolean;
  user: UserProfile | null;
  quota: UserQuota | null;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (accessToken: string, refreshToken: string, user: UserProfile) => void;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  updateQuota: (quota: UserQuota) => void;
  testLogin: () => void;  // Mock 모드 전용
}

const AuthContext = createContext<AuthContextValue | null>(null);

const IS_MOCK = import.meta.env.VITE_ENABLE_MOCK === 'true';

// 테스트용 유저 (Mock 모드 전용)
const TEST_USER: UserProfile = {
  id: 'test-user-001',
  email: 'test@contalktok.kr',
  nickname: '테스트유저',
  provider: 'kakao',
  createdAt: new Date().toISOString(),
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    isLoggedIn: false,
    user: null,
    quota: null,
    isLoading: true,
  });

  const refreshUser = useCallback(async () => {
    try {
      const token = localStorage.getItem('accessToken');
      if (!token) {
        setState({ isLoggedIn: false, user: null, quota: null, isLoading: false });
        return;
      }
      const data = await authApi.me();
      setState({
        isLoggedIn: true,
        user: data.user,
        quota: data.quota,
        isLoading: false,
      });
    } catch {
      setState({ isLoggedIn: false, user: null, quota: null, isLoading: false });
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  // axios interceptor가 토큰 갱신 실패 시 발생시키는 이벤트 수신
  useEffect(() => {
    const handleForceLogout = () => {
      setState({ isLoggedIn: false, user: null, quota: null, isLoading: false });
    };
    window.addEventListener('auth:logout', handleForceLogout);
    return () => window.removeEventListener('auth:logout', handleForceLogout);
  }, []);

  const login = (accessToken: string, refreshToken: string, user: UserProfile) => {
    localStorage.setItem('accessToken', accessToken);
    localStorage.setItem('refreshToken', refreshToken);
    setState((prev) => ({ ...prev, isLoggedIn: true, user }));
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch {
      // ignore
    } finally {
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
      setState({ isLoggedIn: false, user: null, quota: null, isLoading: false });
    }
  };

  const updateQuota = (quota: UserQuota) => {
    setState((prev) => ({ ...prev, quota }));
  };

  // 개발 테스트 전용 — 백엔드 /auth/dev-login 호출 후 실제 JWT 저장
  // MSW 모드: MSW가 가로채서 mock 토큰 반환
  // 실제 백엔드 모드: dev-login API로 실제 JWT 발급 (APP_ENV=development 전용)
  const testLogin = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true }));
    try {
      const res = await fetch('/api/v1/auth/dev-login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`dev-login failed: ${res.status}`);
      const json = await res.json();
      const data = json?.data ?? json;
      const { accessToken, refreshToken, user } = data;
      localStorage.setItem('accessToken', accessToken);
      localStorage.setItem('refreshToken', refreshToken);
      setState({
        isLoggedIn: true,
        user: user ?? TEST_USER,
        quota: { type: 'single', remaining: 99 },
        isLoading: false,
      });
    } catch {
      // 백엔드 연결 불가 시 fallback — 순수 프론트 목업
      setState({
        isLoggedIn: true,
        user: TEST_USER,
        quota: { type: 'single', remaining: 99 },
        isLoading: false,
      });
    }
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, refreshUser, updateQuota, testLogin }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
