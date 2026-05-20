import { useNavigate } from 'react-router-dom';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import PrimaryButton from '../components/PrimaryButton';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

export default function MyPage() {
  const navigate = useNavigate();
  const { isLoggedIn, user, quota, logout } = useAuth();
  const { showToast } = useToast();

  const handleLogout = async () => {
    await logout();
    showToast({ type: 'info', message: '로그아웃되었어요.' });
    navigate('/');
  };

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gray-50 pb-24">
        <NavBar title="내 정보" showBack />
        <main className="max-w-2xl mx-auto px-4 pt-20 text-center py-16">
          <p className="text-4xl mb-4" aria-hidden="true">👤</p>
          <h2 className="text-lg font-semibold text-gray-900 mb-2">로그인이 필요해요</h2>
          <p className="text-sm text-gray-500 mb-6">서비스를 이용하려면 로그인해주세요.</p>
          <PrimaryButton onClick={() => navigate('/login')}>로그인하기</PrimaryButton>
        </main>
        <BottomNavBar />
      </div>
    );
  }

  const quotaLabel =
    quota?.type === 'none'
      ? '이용권 없음'
      : quota?.type === 'pass_3month'
      ? `3개월 패스 (${quota.remaining === -1 ? '무제한' : `${quota.remaining}회 남음`})`
      : `건당 이용권 (${quota?.remaining}회 남음)`;

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar title="내 정보" showBack />

      <main className="max-w-2xl mx-auto px-4 pt-20 pb-6 space-y-4">
        {/* 프로필 카드 */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-card">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-blue-100 rounded-full flex items-center justify-center text-2xl" aria-hidden="true">
              {user?.provider === 'kakao' ? '🟡' : '🔵'}
            </div>
            <div>
              <p className="font-semibold text-gray-900">{user?.nickname}</p>
              <p className="text-sm text-gray-500">{user?.email}</p>
              <p className="text-xs text-gray-400 mt-0.5">
                {user?.provider === 'kakao' ? '카카오 계정' : '구글 계정'}
              </p>
            </div>
          </div>
        </div>

        {/* 이용권 현황 */}
        <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-card">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">이용권 현황</h2>
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">{quotaLabel}</span>
            <PrimaryButton size="sm" variant="secondary" onClick={() => navigate('/payment')}>
              이용권 구매
            </PrimaryButton>
          </div>
          {quota?.passExpiresAt && (
            <p className="text-xs text-gray-400 mt-2">
              만료일: {new Date(quota.passExpiresAt).toLocaleDateString('ko-KR')}
            </p>
          )}
        </div>

        {/* 메뉴 */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-card">
          {[
            { label: '분석 이력', icon: '📋', action: () => showToast({ type: 'info', message: '분석 이력 기능은 v1.1에서 제공될 예정이에요.' }) },
            { label: '결제 이력', icon: '💳', action: () => showToast({ type: 'info', message: '결제 이력 기능은 v1.1에서 제공될 예정이에요.' }) },
            { label: '공지사항', icon: '📢', action: () => {} },
            { label: '고객 지원', icon: '💬', action: () => {} },
          ].map((item, index, arr) => (
            <button
              key={item.label}
              onClick={item.action}
              className={`w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors focus:outline-none ${
                index < arr.length - 1 ? 'border-b border-gray-100' : ''
              }`}
            >
              <span className="flex items-center gap-3 text-sm text-gray-700">
                <span aria-hidden="true">{item.icon}</span>
                {item.label}
              </span>
              <span className="text-gray-300 text-sm" aria-hidden="true">›</span>
            </button>
          ))}
        </div>

        {/* 로그아웃 */}
        <PrimaryButton variant="ghost" size="md" fullWidth onClick={handleLogout}>
          로그아웃
        </PrimaryButton>

        <p className="text-center text-xs text-gray-400">
          계약똑똑 v1.0.0 · {new Date().getFullYear()} 계약똑똑
        </p>
      </main>

      <BottomNavBar />
    </div>
  );
}
