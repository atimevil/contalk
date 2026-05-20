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
}

const AuthContext = createContext<AuthContextValue | null>(null);

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

  return (
    <AuthContext.Provider value={{ ...state, login, logout, refreshUser, updateQuota }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
