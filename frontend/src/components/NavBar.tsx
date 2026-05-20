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
      <header className="fixed top-0 left-0 right-0 bg-white border-b border-gray-200 z-40 h-14">
        <div className="max-w-2xl mx-auto flex items-center justify-between h-full px-4">
          {showBack ? (
            <button
              onClick={handleBack}
              className="flex items-center gap-1 text-gray-700 hover:text-gray-900 font-medium focus:outline-none focus:underline min-w-[44px] min-h-[44px] justify-start"
              aria-label="뒤로가기"
            >
              ←
            </button>
          ) : (
            <div className="w-11" />
          )}

          {title && (
            <h1 className="text-base font-semibold text-gray-900 truncate">{title}</h1>
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
    <header className="fixed top-0 left-0 right-0 bg-white border-b border-gray-200 z-40 h-14">
      <div className="max-w-2xl mx-auto flex items-center justify-between h-full px-4">
        <button
          onClick={() => navigate('/')}
          className="text-lg font-bold text-blue-600 focus:outline-none"
          aria-label="홈으로"
        >
          계약똑똑
        </button>

        <div className="flex items-center gap-2">
          {isLoggedIn ? (
            <button
              onClick={() => navigate('/mypage')}
              className="text-sm text-gray-600 hover:text-gray-900 px-3 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
            >
              내 정보
            </button>
          ) : (
            <button
              onClick={() => navigate('/login')}
              className="text-sm text-blue-600 font-medium hover:text-blue-700 px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors"
            >
              로그인
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
