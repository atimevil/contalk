import { useNavigate, useLocation } from 'react-router-dom';

type NavTab = 'home' | 'upload' | 'checklist' | 'mypage';

interface NavItem {
  id: NavTab;
  label: string;
  path: string;
  iconOutline: string;
  iconActive: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'home', label: '홈', path: '/', iconOutline: '🏠', iconActive: '🏠' },
  { id: 'upload', label: '분석하기', path: '/upload', iconOutline: '📄', iconActive: '📄' },
  { id: 'checklist', label: '체크리스트', path: '/checklist', iconOutline: '✅', iconActive: '✅' },
  { id: 'mypage', label: '내 정보', path: '/mypage', iconOutline: '👤', iconActive: '👤' },
];

function getActiveTab(pathname: string): NavTab {
  if (pathname === '/') return 'home';
  if (pathname.startsWith('/upload') || pathname.startsWith('/analyzing') || pathname.startsWith('/report')) return 'upload';
  if (pathname.startsWith('/checklist')) return 'checklist';
  if (pathname.startsWith('/mypage')) return 'mypage';
  return 'home';
}

export default function BottomNavBar() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const activeTab = getActiveTab(pathname);

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-up safe-area-pb z-40"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
      aria-label="하단 내비게이션"
    >
      <div className="max-w-2xl mx-auto flex items-center h-16">
        {NAV_ITEMS.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => navigate(item.path)}
              className={`flex-1 flex flex-col items-center justify-center gap-0.5 h-full focus:outline-none transition-colors ${
                isActive ? 'text-blue-600' : 'text-gray-500'
              }`}
              aria-label={item.label}
              aria-current={isActive ? 'page' : undefined}
            >
              <span className="text-xl" aria-hidden="true">
                {isActive ? item.iconActive : item.iconOutline}
              </span>
              <span className={`text-xs font-medium ${isActive ? 'text-blue-600' : 'text-gray-500'}`}>
                {item.label}
              </span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
