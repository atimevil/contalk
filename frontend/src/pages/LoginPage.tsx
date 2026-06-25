import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import PrimaryButton from '../components/PrimaryButton';
import { authApi } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import type { AuthResponse } from '../types/api';

interface TermItem {
  id: string;
  label: string;
  required: boolean;
}

const TERMS: TermItem[] = [
  { id: 'termsOfService', label: '서비스 이용약관 (필수)', required: true },
  { id: 'privacyPolicy', label: '개인정보 처리방침 (필수)', required: true },
  { id: 'marketing', label: '마케팅 수신 동의 (선택)', required: false },
];

const IS_DEV = import.meta.env.DEV; // Vite 개발 서버 실행 중이면 true
const IS_DEMO = import.meta.env.VITE_DEMO_MODE === 'true'; // 시연 모드

// 카카오 SDK 초기화
function initKakaoSdk() {
  const appKey = import.meta.env.VITE_KAKAO_APP_KEY;
  if (!appKey || !window.Kakao) return;
  if (!window.Kakao.isInitialized()) {
    window.Kakao.init(appKey);
  }
}

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { login } = useAuth();
  const { showToast } = useToast();
  const from = (location.state as { from?: string })?.from || '/';

  const [isNewUser, setIsNewUser] = useState(false);
  const [termsChecked, setTermsChecked] = useState<Record<string, boolean>>({});

  const allRequired = TERMS.filter((t) => t.required).every((t) => termsChecked[t.id]);
  const allChecked = TERMS.every((t) => termsChecked[t.id]);

  const devLoginMutation = useMutation({
    mutationFn: () => authApi.devLogin(),
    onSuccess: (data) => {
      // login()을 써야 localStorage에 실제 토큰이 저장되어
      // 이후 upload API 등 인증 헤더가 정상 동작한다
      login(data.accessToken, data.refreshToken, data.user);
      showToast({ type: 'success', message: '🧪 테스트 계정으로 로그인됐어요!' });
      navigate(from, { replace: true });
    },
    onError: (err) => {
      console.error('[dev-login] 실패:', err);
      showToast({ type: 'error', message: '백엔드에 연결할 수 없어요. Docker 컨테이너가 실행 중인지 확인해주세요.' });
    },
  });

  const loginMutation = useMutation<AuthResponse, Error, 'kakao' | 'google'>({
    mutationFn: async (provider) => {
      // 데모 모드: MSW mock으로 즉시 처리
      if (IS_DEMO) {
        const mockCode = `mock-oauth-code-${provider}-${Date.now()}`;
        const mockRedirectUri = `${window.location.origin}/oauth/${provider}/callback`;
        if (provider === 'kakao') {
          return authApi.kakaoLogin({ code: mockCode, redirectUri: mockRedirectUri });
        } else {
          return authApi.googleLogin({ code: mockCode, redirectUri: mockRedirectUri });
        }
      }

      // 실제 OAuth 플로우
      if (provider === 'kakao') {
        initKakaoSdk();
        if (!window.Kakao?.isInitialized()) {
          throw new Error('카카오 SDK 초기화 실패');
        }
        // 카카오 로그인 페이지로 리다이렉트 (인가코드 방식)
        const redirectUri = `${window.location.origin}/oauth/kakao/callback`;
        window.Kakao.Auth.authorize({ redirectUri });
        // 리다이렉트되므로 여기서 끝남 — 콜백 페이지에서 code를 백엔드로 전송
        return new Promise(() => {}); // never resolves (redirect happens)
      } else {
        // 구글 OAuth — redirect 방식
        const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
        const redirectUri = `${window.location.origin}/oauth/google/callback`;
        const scope = 'openid email profile';
        const googleAuthUrl = `https://accounts.google.com/o/oauth2/v2/auth?client_id=${clientId}&redirect_uri=${encodeURIComponent(redirectUri)}&response_type=code&scope=${encodeURIComponent(scope)}&access_type=offline&prompt=consent`;
        window.location.href = googleAuthUrl;
        return new Promise(() => {}); // never resolves (redirect happens)
      }
    },
    onSuccess: (data) => {
      login(data.accessToken, data.refreshToken, data.user);

      if (data.isNewUser) {
        setIsNewUser(true);
        return;
      }

      showToast({ type: 'success', message: `${data.user.nickname}님, 환영해요!` });
      navigate(from, { replace: true });
    },
    onError: () => {
      showToast({ type: 'error', message: '로그인에 실패했어요. 다시 시도해 주세요.' });
    },
  });

  const agreeMutation = useMutation({
    mutationFn: () =>
      authApi.agree({
        termsOfService: !!termsChecked['termsOfService'],
        privacyPolicy: !!termsChecked['privacyPolicy'],
        marketing: !!termsChecked['marketing'],
      }),
    onSuccess: () => {
      showToast({ type: 'success', message: '가입이 완료되었어요! 환영해요 🎉' });
      navigate(from, { replace: true });
    },
    onError: () => {
      showToast({ type: 'error', message: '동의 처리에 실패했어요.' });
    },
  });

  const toggleTerm = (id: string) => {
    setTermsChecked((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const toggleAll = () => {
    if (allChecked) {
      setTermsChecked({});
    } else {
      const all = Object.fromEntries(TERMS.map((t) => [t.id, true]));
      setTermsChecked(all);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white/95 backdrop-blur-sm border-b border-slate-200 h-14 flex items-center px-4">
        <button
          onClick={() => navigate(-1)}
          className="text-slate-700 hover:text-slate-900 font-medium focus:outline-none min-w-[44px] min-h-[44px] flex items-center"
          aria-label="뒤로가기"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>
      </header>

      <main className="flex-1 max-w-3xl mx-auto w-full px-4 py-12 flex flex-col items-center">
        {/* 로고 */}
        <div className="flex items-center gap-2 mb-2">
          <div className="w-9 h-9 bg-brand-600 rounded-lg flex items-center justify-center">
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>
          <span className="text-2xl font-extrabold text-brand-900 tracking-tight">계약똑똑</span>
        </div>
        <p className="text-sm text-slate-500 mb-10 text-center">AI 임대차 계약서 분석 서비스</p>

        {!isNewUser ? (
          <>
            <p className="text-base text-slate-700 text-center mb-8 leading-relaxed">
              계약서 분석을 시작하려면<br />로그인이 필요해요.
            </p>

            {/* 소셜 로그인 버튼 */}
            <div className="w-full max-w-sm space-y-3">
              <PrimaryButton
                size="lg"
                fullWidth
                loading={loginMutation.isPending && loginMutation.variables === 'kakao'}
                onClick={() => loginMutation.mutate('kakao')}
                className="!bg-yellow-400 !text-slate-900 hover:!bg-yellow-500"
              >
                <span className="mr-2" aria-hidden="true">🟡</span>
                카카오로 계속하기
              </PrimaryButton>

              <PrimaryButton
                size="lg"
                fullWidth
                variant="secondary"
                loading={loginMutation.isPending && loginMutation.variables === 'google'}
                onClick={() => loginMutation.mutate('google')}
              >
                <span className="mr-2" aria-hidden="true">🔵</span>
                구글로 계속하기
              </PrimaryButton>

              {/* 개발 테스트 전용 — Vite 개발 서버에서만 표시 */}
              {IS_DEV && (
                <>
                  <div className="flex items-center gap-2 my-2">
                    <div className="flex-1 h-px bg-slate-200" />
                    <span className="text-xs text-slate-400">개발 테스트</span>
                    <div className="flex-1 h-px bg-slate-200" />
                  </div>
                  <button
                    disabled={devLoginMutation.isPending}
                    onClick={() => devLoginMutation.mutate()}
                    className="w-full py-3 px-4 rounded-xl border-2 border-dashed border-slate-300 text-sm text-slate-500 hover:border-brand-400 hover:text-brand-600 hover:bg-brand-50 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-600 disabled:opacity-50"
                  >
                    {devLoginMutation.isPending ? '로그인 중...' : '🧪 로그인 없이 바로 테스트'}
                  </button>
                </>
              )}
            </div>

            <p className="text-xs text-slate-400 mt-8 text-center">
              이미 계정이 있으신가요?<br />소셜 로그인으로 자동으로 연결됩니다.
            </p>
          </>
        ) : (
          <>
            <p className="text-base text-slate-700 text-center mb-6">
              처음 오셨군요! 약관에 동의해주세요.
            </p>

            <div className="w-full max-w-sm">
              {/* 전체 동의 */}
              <div className="bg-white border border-slate-200 rounded-xl p-4 mb-3 shadow-card">
                <button
                  onClick={toggleAll}
                  className="w-full flex items-center gap-3 text-left focus:outline-none"
                  aria-pressed={allChecked}
                >
                  <span
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                      allChecked ? 'bg-brand-600 border-brand-600 text-white' : 'border-slate-300'
                    }`}
                    aria-hidden="true"
                  >
                    {allChecked && '✓'}
                  </span>
                  <span className="font-semibold text-slate-900">전체 동의</span>
                </button>

                <div className="mt-3 space-y-3 pl-9">
                  {TERMS.map((term) => (
                    <div key={term.id} className="flex items-center justify-between">
                      <button
                        onClick={() => toggleTerm(term.id)}
                        className="flex items-center gap-2 text-left focus:outline-none"
                        aria-pressed={!!termsChecked[term.id]}
                      >
                        <span
                          className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                            termsChecked[term.id] ? 'bg-brand-600 border-brand-600 text-white' : 'border-slate-300'
                          }`}
                          aria-hidden="true"
                        >
                          {termsChecked[term.id] && <span className="text-xs">✓</span>}
                        </span>
                        <span className={`text-sm ${term.required ? 'text-slate-900' : 'text-slate-500'}`}>
                          {term.label}
                        </span>
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          showToast({ type: 'info', message: '약관 전문은 고객센터(support@contalktok.kr)로 요청하실 수 있어요.' })
                        }
                        className="text-xs text-brand-600 hover:underline focus:outline-none"
                      >
                        보기
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {!allRequired && (
                <p className="text-sm text-red-600 mb-3 flex items-center gap-1" role="alert">
                  <span>⚠️</span> 필수 약관에 동의해주세요
                </p>
              )}

              <PrimaryButton
                size="lg"
                fullWidth
                disabled={!allRequired}
                loading={agreeMutation.isPending}
                onClick={() => agreeMutation.mutate()}
              >
                동의하고 시작하기
              </PrimaryButton>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
