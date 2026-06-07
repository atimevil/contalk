import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

interface NavBarProps {
  title?: string;
  showBack?: boolean;
  onBack?: () => void;
  rightActions?: React.ReactNode;
}

export default function NavBar({ title, showBack = false, onBack, rightActions }: NavBarProps) {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuth();

  const handleBack = () => {
    if (onBack) {
      onBack();
    } else {
      navigate(-1);
    }
  };

  // 상단 앱 바 (뒤로가기가 있는 경우)
  if (showBack || title) {
    return (
      <header className="fixed top-0 left-0 right-0 bg-white/95 backdrop-blur-sm border-b border-slate-200 z-40 h-14">
        <div className="max-w-3xl mx-auto flex items-center justify-between h-full px-4">
          {showBack ? (
            <button
              onClick={handleBack}
              className="flex items-center gap-1 text-slate-700 hover:text-slate-900 font-medium focus:outline-none min-w-[44px] min-h-[44px] justify-start"
              aria-label="뒤로가기"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
              </svg>
            </button>
          ) : (
            <div className="w-11" />
          )}

          {title && (
            <h1 className="text-sm font-bold text-slate-900 tracking-tight truncate">{title}</h1>
          )}

          <div className="flex items-center gap-2 min-w-[44px] justify-end">
            {rightActions}
          </div>
        </div>
      </header>
    );
  }

  // 랜딩 홈 네비게이션
  return (
    <header className="fixed top-0 left-0 right-0 bg-white/95 backdrop-blur-sm border-b border-slate-200 z-40 h-14">
      <div className="max-w-3xl mx-auto flex items-center justify-between h-full px-4">
        <button
          onClick={() => navigate('/')}
          className="flex items-center gap-2 focus:outline-none"
          aria-label="홈으로"
        >
          <div className="w-7 h-7 bg-brand-600 rounded-lg flex items-center justify-center">
            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
            </svg>
          </div>
          <span className="text-base font-bold text-brand-900 tracking-tight">계약똑똑</span>
        </button>

        <div className="flex items-center gap-2">
          {isLoggedIn ? (
            <button
              onClick={() => navigate('/mypage')}
              className="text-sm text-slate-600 hover:text-slate-900 px-3 py-1.5 rounded-lg hover:bg-slate-100 transition-colors font-medium"
            >
              내 정보
            </button>
          ) : (
            <button
              onClick={() => navigate('/login')}
              className="text-sm text-brand-600 font-bold hover:text-brand-700 px-4 py-2 rounded-lg bg-brand-50 hover:bg-brand-100 transition-colors border border-brand-200"
            >
              로그인
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
