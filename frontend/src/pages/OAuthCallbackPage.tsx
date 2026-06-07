import { useEffect, useRef } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { authApi } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

/**
 * OAuth 콜백 페이지
 * /oauth/:provider/callback?code=xxx 형태로 리다이렉트됨
 * code를 백엔드로 전송하여 토큰을 발급받는다.
 */
export default function OAuthCallbackPage() {
  const { provider } = useParams<{ provider: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { login } = useAuth();
  const { showToast } = useToast();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const code = searchParams.get('code');
    if (!code || !provider) {
      showToast({ type: 'error', message: '로그인 정보가 올바르지 않아요.' });
      navigate('/login', { replace: true });
      return;
    }

    const redirectUri = `${window.location.origin}/oauth/${provider}/callback`;

    const doLogin = async () => {
      try {
        const data =
          provider === 'kakao'
            ? await authApi.kakaoLogin({ code, redirectUri })
            : await authApi.googleLogin({ code, redirectUri });

        login(data.accessToken, data.refreshToken, data.user);

        if (data.isNewUser) {
          // 신규 유저면 약관 동의 필요 — 로그인 페이지로 (state로 전달)
          navigate('/login', { replace: true, state: { isNewUser: true } });
        } else {
          showToast({ type: 'success', message: `${data.user.nickname || ''}님, 환영해요!` });
          navigate('/', { replace: true });
        }
      } catch {
        showToast({ type: 'error', message: '로그인에 실패했어요. 다시 시도해 주세요.' });
        navigate('/login', { replace: true });
      }
    };

    doLogin();
  }, [provider, searchParams, navigate, login, showToast]);

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full mx-auto mb-4" />
        <p className="text-slate-600">로그인 처리 중...</p>
      </div>
    </div>
  );
}
