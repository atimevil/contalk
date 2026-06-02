import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import PrimaryButton from '../components/PrimaryButton';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { analysisApi } from '../api/analysis';
import { paymentApi } from '../api/payment';

type ActiveTab = 'analysis' | 'payment';

interface AnalysisHistoryItem {
  reportId?: string;
  report_id?: string;
  createdAt?: string;
  created_at?: string;
  contractType?: string;
  contract_type?: string;
  riskScore?: number;
  risk_score?: number;
  riskLevel?: string;
  risk_level?: string;
}

interface PaymentHistoryItem {
  id: string;
  merchantUid: string;
  amount: number;
  status: string;
  plan: string;
  createdAt: string;
}

export default function MyPage() {
  const navigate = useNavigate();
  const { isLoggedIn, user, quota, logout } = useAuth();
  const { showToast } = useToast();

  // 탭 상태 및 데이터 상태
  const [activeTab, setActiveTab] = useState<ActiveTab>('analysis');
  const [analyses, setAnalyses] = useState<AnalysisHistoryItem[]>([]);
  const [payments, setPayments] = useState<PaymentHistoryItem[]>([]);
  
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingPayments, setLoadingPayments] = useState(false);

  // 모달 제어 상태
  const [isNoticeOpen, setIsNoticeOpen] = useState(false);
  const [isSupportOpen, setIsSupportOpen] = useState(false);
  const [openNoticeIndex, setOpenNoticeIndex] = useState<number | null>(null);

  // 1. 분석 이력 로드
  useEffect(() => {
    if (isLoggedIn && activeTab === 'analysis') {
      setLoadingHistory(true);
      analysisApi
        .getHistory(1, 20)
        .then((res) => {
          setAnalyses(res.analyses);
        })
        .catch((err) => {
          console.error('분석 이력 가져오기 실패:', err);
        })
        .finally(() => {
          setLoadingHistory(false);
        });
    }
  }, [isLoggedIn, activeTab]);

  // 2. 결제 이력 로드
  useEffect(() => {
    if (isLoggedIn && activeTab === 'payment') {
      setLoadingPayments(true);
      paymentApi
        .history()
        .then((res) => {
          // res는 { payments: [...] } 형식으로 추정
          const items = (res as any).payments || [];
          setPayments(items);
        })
        .catch((err) => {
          console.error('결제 이력 가져오기 실패:', err);
        })
        .finally(() => {
          setLoadingPayments(false);
        });
    }
  }, [isLoggedIn, activeTab]);

  const handleLogout = async () => {
    await logout();
    showToast({ type: 'info', message: '로그아웃되었어요.' });
    navigate('/');
  };

  if (!isLoggedIn) {
    return (
      <div className="min-h-screen bg-gray-50 pb-24">
        <NavBar title="내 정보" showBack />
        <main className="max-w-2xl mx-auto px-4 pt-16 text-center py-16">
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

  // 공지사항 더미 데이터
  const NOTICES = [
    {
      title: '임시',
      date: new Date().toLocaleDateString('ko-KR'),
      content: '임시',
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar title="내 정보" showBack />

      <main className="max-w-2xl mx-auto px-4 pt-16 pb-6 space-y-4">
        {/* 프로필 카드 */}
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-blue-100 rounded-full flex items-center justify-center text-2xl" aria-hidden="true">
              {user?.provider === 'kakao' ? '🟡' : '🔵'}
            </div>
            <div>
              <p className="font-bold text-gray-900 text-base">{user?.nickname}</p>
              <p className="text-sm text-gray-500">{user?.email}</p>
              <p className="text-xs text-gray-400 mt-1">
                {user?.provider === 'kakao' ? '카카오 간편 로그인 계정' : '구글 간편 로그인 계정'}
              </p>
            </div>
          </div>
        </div>

        {/* 이용권 현황 */}
        <div className="bg-white border border-gray-200 rounded-2xl p-5 shadow-sm">
          <h2 className="text-sm font-bold text-gray-700 mb-3">내 분석 이용권</h2>
          <div className="flex items-center justify-between">
            <span className="text-base font-bold text-blue-600">{quotaLabel}</span>
            <PrimaryButton size="sm" variant="secondary" onClick={() => navigate('/payment')}>
              충전하기
            </PrimaryButton>
          </div>
          {quota?.passExpiresAt && (
            <p className="text-xs text-gray-400 mt-2.5">
              프리패스 만료일: {new Date(quota.passExpiresAt).toLocaleDateString('ko-KR')}
            </p>
          )}
        </div>

        {/* 📋 💳 상시 통합 이력 탭 섹션 */}
        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm flex flex-col">
          {/* 탭 버튼 헤더 */}
          <div className="flex border-b border-gray-100">
            <button
              onClick={() => setActiveTab('analysis')}
              className={`flex-1 py-3 text-sm font-bold text-center border-b-2 transition-all ${
                activeTab === 'analysis'
                  ? 'border-blue-600 text-blue-600 bg-blue-50/10'
                  : 'border-transparent text-gray-500 hover:text-gray-900 bg-white'
              }`}
            >
              분석 이력 📋
            </button>
            <button
              onClick={() => setActiveTab('payment')}
              className={`flex-1 py-3 text-sm font-bold text-center border-b-2 transition-all ${
                activeTab === 'payment'
                  ? 'border-blue-600 text-blue-600 bg-blue-50/10'
                  : 'border-transparent text-gray-500 hover:text-gray-900 bg-white'
              }`}
            >
              결제 영수증 💳
            </button>
          </div>

          {/* 탭 콘텐츠 영역 */}
          <div className="p-4 min-h-[180px] max-h-[440px] overflow-y-auto scroll-hidden">
            {activeTab === 'analysis' ? (
              loadingHistory ? (
                <div className="flex flex-col items-center justify-center py-10 space-y-2">
                  <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent" />
                  <p className="text-xs text-gray-400">분석 이력을 긁어오는 중...</p>
                </div>
              ) : analyses.length === 0 ? (
                <div className="text-center py-12 space-y-3 bg-gray-50/50 rounded-2xl border border-dashed border-gray-200">
                  <p className="text-3xl">🔍</p>
                  <p className="text-sm font-semibold text-gray-800">아직 분석한 계약서가 없어요</p>
                  <p className="text-xs text-gray-400 max-w-[240px] mx-auto leading-relaxed">
                    내 소중한 보증금을 지키기 위해 계약서를 분석해 보세요!
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {analyses.map((item) => {
                    const reportId = item.reportId || item.report_id || '';
                    const createdAt = item.createdAt || item.created_at || '';
                    const contractType = item.contractType || item.contract_type || '';
                    const riskScore = item.riskScore !== undefined ? item.riskScore : (item.risk_score ?? 0);
                    const riskLevel = item.riskLevel || item.risk_level || 'safe';

                    const typeLabel = contractType === 'jeonse' ? '전세' : contractType === 'monthly' ? '월세' : '미지정';
                    const typeColor = contractType === 'jeonse' ? 'bg-blue-600' : contractType === 'monthly' ? 'bg-indigo-600' : 'bg-gray-400';
                    
                    // 점수 대역별 고품격 색상 테마 및 서클 정의
                    const isHighRisk = riskLevel === 'high' || riskLevel === 'medium';
                    const theme = isHighRisk
                      ? {
                          border: 'border-red-100 hover:border-red-300',
                          bg: 'bg-gradient-to-br from-white to-red-50/10',
                          badge: 'bg-red-50 text-red-600 border-red-100',
                          scoreColor: 'text-red-600',
                          iconBg: 'bg-red-50',
                          icon: '🚨',
                          badgeLabel: '위험',
                        }
                      : riskLevel === 'caution'
                      ? {
                          border: 'border-amber-100 hover:border-amber-300',
                          bg: 'bg-gradient-to-br from-white to-amber-50/10',
                          badge: 'bg-amber-50 text-amber-600 border-amber-100',
                          scoreColor: 'text-amber-600',
                          iconBg: 'bg-amber-50',
                          icon: '⚠️',
                          badgeLabel: '주의',
                        }
                      : {
                          border: 'border-green-100 hover:border-green-300',
                          bg: 'bg-gradient-to-br from-white to-green-50/10',
                          badge: 'bg-green-50 text-green-700 border-green-100',
                          scoreColor: 'text-green-600',
                          iconBg: 'bg-green-50',
                          icon: '🛡️',
                          badgeLabel: '안전',
                        };

                    return (
                      <button
                        key={reportId}
                        onClick={() => navigate(`/report/${reportId}`)}
                        className={`group w-full text-left rounded-2xl border-2 p-4 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md flex items-center justify-between gap-4 ${theme.border} ${theme.bg}`}
                      >
                        <div className="flex items-center gap-4 min-w-0 flex-1">
                          {/* 왼쪽 아이콘 영역 */}
                          <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-xl flex-shrink-0 shadow-inner transition-transform group-hover:scale-105 ${theme.iconBg}`} aria-hidden="true">
                            {theme.icon}
                          </div>

                          {/* 중앙 정보 텍스트 */}
                          <div className="flex-1 min-w-0 space-y-1.5">
                            <div className="flex items-center gap-1.5">
                              <span className={`text-[9px] font-extrabold text-white px-2 py-0.5 rounded tracking-wider ${typeColor}`}>
                                {typeLabel}
                              </span>
                              <span className={`text-[9px] font-extrabold border px-2 py-0.5 rounded-full ${theme.badge}`}>
                                {theme.badgeLabel}
                              </span>
                            </div>
                            <p className="font-bold text-sm text-gray-900 truncate">
                              {typeLabel} 계약 분석 결과
                            </p>
                            <p className="text-[10px] text-gray-400 font-medium">
                              분석일: {createdAt ? new Date(createdAt).toLocaleDateString('ko-KR') : '-'}
                            </p>
                          </div>
                        </div>

                        {/* 오른쪽 점수 및 화살표 영역 */}
                        <div className="text-right flex-shrink-0 flex items-center gap-3">
                          <div className="flex flex-col items-end">
                            <span className={`text-base font-extrabold tracking-tight ${theme.scoreColor}`}>
                              {riskScore}
                              <span className="text-[10px] font-bold text-gray-400 ml-0.5">점</span>
                            </span>
                            <span className="text-[9px] font-semibold text-gray-400 uppercase tracking-wider">안전 점수</span>
                          </div>
                          <span className="text-gray-300 text-lg transition-colors group-hover:text-blue-500 font-bold">›</span>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )
            ) : loadingPayments ? (
              <div className="flex flex-col items-center justify-center py-8 space-y-2">
                <div className="animate-spin rounded-full h-7 w-7 border-2 border-blue-500 border-t-transparent" />
                <p className="text-xs text-gray-400">결제 내역을 조회하는 중...</p>
              </div>
            ) : payments.length === 0 ? (
              <div className="text-center py-10 space-y-2">
                <p className="text-2xl">💳</p>
                <p className="text-sm font-semibold text-gray-800">아직 결제한 내역이 없어요</p>
                <p className="text-xs text-gray-400">이용권을 구매하여 첫 분석을 시작해 보세요.</p>
              </div>
            ) : (
              <div className="space-y-2.5">
                {payments.map((item) => {
                  const planLabel = item.plan === 'single' ? '단건 분석 이용권' : '3개월 프리패스';
                  const isPaid = item.status === 'paid';
                  return (
                    <div
                      key={item.id}
                      className="flex items-center justify-between p-3.5 rounded-xl border border-gray-100 bg-white shadow-sm"
                    >
                      <div className="space-y-1">
                        <p className="font-bold text-sm text-gray-800">{planLabel}</p>
                        <p className="text-[11px] text-gray-400">
                          결제일: {new Date(item.createdAt).toLocaleDateString('ko-KR')}
                        </p>
                        <p className="text-[10px] text-gray-300">주문번호: {item.merchantUid}</p>
                      </div>
                      <div className="text-right space-y-1">
                        <p className="text-sm font-extrabold text-blue-600">
                          {item.amount.toLocaleString()}원
                        </p>
                        <span className={`text-[10px] px-2 py-0.5 rounded font-bold ${
                          isPaid ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'
                        }`}>
                          {isPaid ? '결제 완료' : '결제 실패'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* 📢 💬 더보기 편의 메뉴 섹션 */}
        <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
          {[
            { label: '공지사항', icon: '📢', action: () => setIsNoticeOpen(true) },
            { label: '고객 지원', icon: '💬', action: () => setIsSupportOpen(true) },
          ].map((item, index, arr) => (
            <button
              key={item.label}
              onClick={item.action}
              className={`w-full flex items-center justify-between px-5 py-4 hover:bg-gray-50 transition-colors focus:outline-none ${
                index < arr.length - 1 ? 'border-b border-gray-100' : ''
              }`}
            >
              <span className="flex items-center gap-3 text-sm font-semibold text-gray-700">
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

      {isNoticeOpen && (
        <div 
          onClick={() => {
            setIsNoticeOpen(false);
            setOpenNoticeIndex(null);
          }}
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-2xl max-w-md w-full p-5 max-h-[80vh] flex flex-col shadow-xl animate-fade-in"
          >
            <div className="flex items-center justify-between border-b border-gray-100 pb-3 mb-4">
              <h3 className="font-extrabold text-gray-900 text-base">공지사항 📢</h3>
              <button
                onClick={() => {
                  setIsNoticeOpen(false);
                  setOpenNoticeIndex(null);
                }}
                className="text-gray-400 hover:text-gray-600 text-xl font-bold w-8 h-8 flex items-center justify-center"
              >
                ×
              </button>
            </div>

            <div className="flex-1 overflow-y-auto space-y-2.5 pr-1 scroll-hidden">
              {NOTICES.map((notice, idx) => {
                const isOpen = openNoticeIndex === idx;
                return (
                  <div key={idx} className="border border-gray-100 rounded-xl overflow-hidden shadow-sm">
                    <button
                      onClick={() => setOpenNoticeIndex(isOpen ? null : idx)}
                      className="w-full flex flex-col p-4 bg-gray-50/50 hover:bg-gray-50 transition-colors text-left"
                    >
                      <span className="text-xs text-gray-400 mb-1">{notice.date}</span>
                      <p className="font-bold text-sm text-gray-800 leading-snug">{notice.title}</p>
                    </button>
                    {isOpen && (
                      <div className="p-4 bg-white border-t border-gray-50 text-sm text-gray-600 leading-relaxed whitespace-pre-line">
                        {notice.content}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* 💬 고객지원 팝업 모달 */}
      {isSupportOpen && (
        <div 
          onClick={() => setIsSupportOpen(false)}
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        >
          <div 
            onClick={(e) => e.stopPropagation()}
            className="bg-white rounded-2xl max-w-sm w-full p-5 shadow-xl animate-fade-in text-center space-y-4"
          >
            <div className="flex items-center justify-between border-b border-gray-100 pb-3">
              <h3 className="font-extrabold text-gray-900 text-base">고객지원 💬</h3>
              <button
                onClick={() => setIsSupportOpen(false)}
                className="text-gray-400 hover:text-gray-600 text-xl font-bold w-8 h-8 flex items-center justify-center"
              >
                ×
              </button>
            </div>

            <div className="py-2 space-y-3">
              <p className="text-3xl">🤝</p>
              <h4 className="font-bold text-gray-800 text-base">계약똑똑 고객센터</h4>
              <p className="text-xs text-gray-500 leading-relaxed">
                이용 도중 불편한 점이나 계약서 파싱 오류 등이 있으시면<br />
                언제든지 아래 창구로 문의해 주세요.
              </p>
            </div>

            <div className="space-y-2">
              <a
                href="https://pf.kakao.com"
                target="_blank"
                rel="noopener noreferrer"
                className="w-full h-11 bg-yellow-400 text-yellow-950 font-bold rounded-xl flex items-center justify-center gap-2 hover:bg-yellow-500 transition-colors shadow-sm text-sm"
              >
                🟡 카카오톡 1:1 빠른 상담
              </a>
              <a
                href="mailto:support@contalktok.kr?subject=[계약똑똑 문의]"
                className="w-full h-11 bg-blue-50 text-blue-700 font-bold rounded-xl flex items-center justify-center gap-2 hover:bg-blue-100 transition-colors shadow-sm text-sm border border-blue-100"
              >
                ✉️ 이메일로 1:1 문의하기
              </a>
            </div>

            <div className="bg-gray-50 rounded-xl p-3 text-[11px] text-gray-500 text-left space-y-1.5 leading-relaxed">
              <p>⏰ 운영시간: 평일 10:00 ~ 18:00 (주말 및 공휴일 휴무)</p>
              <p>📧 이메일: support@contalktok.kr</p>
              <p>계약서 오파싱 제보 시, 해당 이미지 파일과 아이디를 이메일로 보내주시면 신속하게 이용권을 보상 충전해 드립니다.</p>
            </div>
          </div>
        </div>
      )}

      <BottomNavBar />
    </div>
  );
}
