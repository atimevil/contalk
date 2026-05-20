import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import PrimaryButton from '../components/PrimaryButton';
import { authApi } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

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

  const loginMutation = useMutation({
    mutationFn: async (provider: 'kakao' | 'google') => {
      // MSW 목업 — 실제로는 OAuth 코드를 받아서 전송
      const mockCode = `mock-oauth-code-${provider}-${Date.now()}`;
      const mockRedirectUri = `${window.location.origin}/oauth/${provider}/callback`;

      if (provider === 'kakao') {
        return authApi.kakaoLogin({ code: mockCode, redirectUri: mockRedirectUri });
      } else {
        return authApi.googleLogin({ code: mockCode, redirectUri: mockRedirectUri });
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
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 h-14 flex items-center px-4">
        <button
          onClick={() => navigate(-1)}
          className="text-gray-700 hover:text-gray-900 font-medium focus:outline-none min-w-[44px] min-h-[44px] flex items-center"
          aria-label="뒤로가기"
        >
          ←
        </button>
      </header>

      <main className="flex-1 max-w-2xl mx-auto w-full px-4 py-12 flex flex-col items-center">
        {/* 로고 */}
        <div className="text-4xl font-bold text-blue-600 mb-2" aria-label="계약똑똑">
          계약똑똑
        </div>
        <p className="text-sm text-gray-500 mb-10 text-center">AI 계약서 분석 서비스</p>

        {!isNewUser ? (
          <>
            <p className="text-base text-gray-700 text-center mb-8 leading-relaxed">
              계약서 분석을 시작하려면<br />로그인이 필요해요.
            </p>

            {/* 소셜 로그인 버튼 */}
            <div className="w-full max-w-sm space-y-3">
              <PrimaryButton
                size="lg"
                fullWidth
                loading={loginMutation.isPending && loginMutation.variables === 'kakao'}
                onClick={() => loginMutation.mutate('kakao')}
                className="!bg-yellow-400 !text-gray-900 hover:!bg-yellow-500"
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
            </div>

            <p className="text-xs text-gray-400 mt-8 text-center">
              이미 계정이 있으신가요?<br />소셜 로그인으로 자동으로 연결됩니다.
            </p>
          </>
        ) : (
          <>
            <p className="text-base text-gray-700 text-center mb-6">
              처음 오셨군요! 약관에 동의해주세요.
            </p>

            <div className="w-full max-w-sm">
              {/* 전체 동의 */}
              <div className="bg-white border border-gray-200 rounded-xl p-4 mb-3 shadow-card">
                <button
                  onClick={toggleAll}
                  className="w-full flex items-center gap-3 text-left focus:outline-none"
                  aria-pressed={allChecked}
                >
                  <span
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors ${
                      allChecked ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300'
                    }`}
                    aria-hidden="true"
                  >
                    {allChecked && '✓'}
                  </span>
                  <span className="font-semibold text-gray-900">전체 동의</span>
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
                            termsChecked[term.id] ? 'bg-blue-600 border-blue-600 text-white' : 'border-gray-300'
                          }`}
                          aria-hidden="true"
                        >
                          {termsChecked[term.id] && <span className="text-xs">✓</span>}
                        </span>
                        <span className={`text-sm ${term.required ? 'text-gray-900' : 'text-gray-500'}`}>
                          {term.label}
                        </span>
                      </button>
                      <button className="text-xs text-blue-600 hover:underline focus:outline-none">
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
