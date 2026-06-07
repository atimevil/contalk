import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import ClauseCard from '../components/ClauseCard';
import PrimaryButton from '../components/PrimaryButton';
import SkeletonLoader from '../components/SkeletonLoader';
import { analysisApi } from '../api/analysis';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

const FREE_PREVIEW_COUNT = 3; // 무료 미리보기 조항 수

type FilterTab = 'all' | 'danger' | 'caution' | 'safe';

const FILTER_TABS: { id: FilterTab; label: string }[] = [
  { id: 'all', label: '전체' },
  { id: 'danger', label: '위험' },
  { id: 'caution', label: '주의' },
  { id: 'safe', label: '정상' },
];

export default function ResultPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { quota } = useAuth();
  const [activeFilter, setActiveFilter] = useState<FilterTab>('all');
  const [isDownloading, setIsDownloading] = useState(false);

  // 무료 유저 판별: quota가 없거나 type이 'none' 또는 'free_trial'이면 일부 블러
  const isPaidUser = quota && quota.type !== 'none' && quota.type !== 'free_trial';

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['analysis-result', reportId],
    queryFn: () => analysisApi.getResult(reportId!),
    enabled: !!reportId,
    staleTime: 5 * 60 * 1000,
  });

  const handleDownloadPdf = async () => {
    if (!reportId) return;
    setIsDownloading(true);
    try {
      const blob = await analysisApi.downloadPdf(reportId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `contract_analysis_${reportId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      showToast({ type: 'success', message: 'PDF 다운로드를 시작해요.' });
    } catch {
      showToast({ type: 'error', message: 'PDF 다운로드에 실패했어요.' });
    } finally {
      setIsDownloading(false);
    }
  };

  const handleShare = async () => {
    const shareData = {
      title: '계약똑똑 분석 결과',
      text: '계약서 위험 분석 결과를 확인해보세요.',
      url: window.location.href,
    };
    if (navigator.share) {
      try {
        await navigator.share(shareData);
      } catch {
        // 사용자 취소
      }
    } else {
      await navigator.clipboard.writeText(window.location.href);
      showToast({ type: 'success', message: '링크가 복사되었어요.' });
    }
  };

  const filteredClauses =
    data?.clauses.filter((c) => {
      if (activeFilter === 'all') return true;
      if (activeFilter === 'danger') return c.risk === 'high' || c.risk === 'medium';
      return c.risk === activeFilter;
    }) ?? [];

  const riskScoreColor =
    (data?.riskScore ?? 0) >= 40
      ? 'text-red-600'
      : (data?.riskScore ?? 0) >= 20
      ? 'text-amber-500'
      : 'text-green-600';

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar
        title="분석 결과"
        showBack
        rightActions={
          <div className="flex gap-2">
            <button
              onClick={handleShare}
              className="text-sm text-gray-500 hover:text-gray-700 px-2 py-1 rounded focus:outline-none"
              aria-label="결과 공유"
            >
              공유
            </button>
            <button
              onClick={handleDownloadPdf}
              disabled={isDownloading}
              className="text-sm text-blue-600 hover:text-blue-700 px-2 py-1 rounded focus:outline-none disabled:opacity-50"
              aria-label="PDF 저장"
            >
              {isDownloading ? '저장 중...' : '저장'}
            </button>
          </div>
        }
      />

      <main className="max-w-2xl mx-auto px-4 pt-20 pb-6 space-y-5">
        {/* 로딩 */}
        {isLoading && (
          <>
            <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-card animate-pulse">
              <div className="h-6 bg-gray-200 rounded w-1/2 mb-4" />
              <div className="h-4 bg-gray-200 rounded mb-2" />
              <div className="h-4 bg-gray-200 rounded w-3/4" />
            </div>
            <SkeletonLoader variant="clause-card" count={5} />
          </>
        )}

        {/* 에러 */}
        {isError && !isLoading && (
          <div className="text-center py-16">
            <p className="text-4xl mb-3" aria-hidden="true">😢</p>
            <h2 className="text-lg font-semibold text-gray-900 mb-2">결과를 불러오지 못했어요</h2>
            <p className="text-sm text-gray-500 mb-6">다시 시도해주세요.</p>
            <PrimaryButton onClick={() => refetch()}>다시 시도</PrimaryButton>
          </div>
        )}

        {/* 결과 */}
        {data && !isLoading && (
          <>
            {/* 종합 위험도 카드 */}
            <div className="bg-white border border-gray-200 rounded-xl p-5 shadow-card">
              <div className="flex items-center gap-2 mb-4">
                <span className="text-lg" aria-hidden="true">📊</span>
                <h2 className="text-base font-semibold text-gray-900">종합 위험도 점수</h2>
              </div>

              <div className="flex items-center gap-4 mb-4">
                <div className="flex-1 bg-gray-200 rounded-full h-3 overflow-hidden">
                  <div
                    className={`h-3 rounded-full transition-all duration-700 ${
                      data.riskScore >= 40 ? 'bg-red-500' : data.riskScore >= 20 ? 'bg-amber-500' : 'bg-green-500'
                    }`}
                    style={{ width: `${data.riskScore}%` }}
                    role="progressbar"
                    aria-valuenow={data.riskScore}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label={`위험도 점수 ${data.riskScore}점`}
                  />
                </div>
                <span className={`text-2xl font-bold tabular-nums ${riskScoreColor}`}>
                  {data.riskScore}점
                </span>
              </div>

              <div className="flex flex-wrap gap-2">
                <span className="inline-flex items-center gap-1.5 text-sm bg-red-50 text-red-600 border border-red-200 rounded-lg px-3 py-1.5">
                  🚨 위험 <strong>{(data.summary.high ?? 0) + (data.summary.medium ?? 0)}개</strong>
                </span>
                <span className="inline-flex items-center gap-1.5 text-sm bg-amber-50 text-amber-600 border border-amber-200 rounded-lg px-3 py-1.5">
                  ⚠️ 주의 <strong>{data.summary.caution}개</strong>
                </span>
                <span className="inline-flex items-center gap-1.5 text-sm bg-green-50 text-green-700 border border-green-200 rounded-lg px-3 py-1.5">
                  ✅ 정상 <strong>{data.summary.safe}개</strong>
                </span>
              </div>
            </div>

            {/* 필터 탭 */}
            <div className="flex gap-2 overflow-x-auto scroll-hidden -mx-4 px-4 pb-1">
              {FILTER_TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveFilter(tab.id)}
                  className={`flex-shrink-0 px-4 py-2 rounded-full text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    activeFilter === tab.id
                      ? 'bg-blue-600 text-white'
                      : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
                  }`}
                  aria-pressed={activeFilter === tab.id}
                >
                  {tab.label}
                  {(() => {
                    if (tab.id === 'all') return null;
                    const count = tab.id === 'danger'
                      ? (data.summary.high ?? 0) + (data.summary.medium ?? 0)
                      : data.summary[tab.id as keyof typeof data.summary] ?? 0;
                    if (count === 0) return null;
                    return (
                      <span className="ml-1.5 text-xs opacity-80">
                        {count}
                      </span>
                    );
                  })()}
                </button>
              ))}
            </div>

            {/* 조항 목록 */}
            {filteredClauses.length === 0 ? (
              <div className="text-center py-12">
                <p className="text-4xl mb-3" aria-hidden="true">✅</p>
                <p className="text-base text-gray-600">
                  {activeFilter === 'all'
                    ? '위험 조항이 발견되지 않았어요'
                    : `해당 위험도의 조항이 없어요`}
                </p>
              </div>
            ) : (
              <div className="space-y-4" aria-label={`${activeFilter === 'all' ? '전체' : activeFilter} 조항 목록`}>
                {filteredClauses.map((clause, index) => {
                  const isLocked = !isPaidUser && index >= FREE_PREVIEW_COUNT;

                  if (isLocked) {
                    return (
                      <div key={clause.id} className="relative">
                        <div className="blur-[6px] pointer-events-none select-none" aria-hidden="true">
                          <ClauseCard clause={clause} />
                        </div>
                        {index === FREE_PREVIEW_COUNT && (
                          <div className="absolute inset-0 flex flex-col items-center justify-center bg-white/70 backdrop-blur-sm rounded-xl border border-slate-200">
                            <svg className="w-8 h-8 text-brand-600 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
                            </svg>
                            <p className="text-sm font-bold text-slate-900 mb-1">
                              나머지 {filteredClauses.length - FREE_PREVIEW_COUNT}개 조항
                            </p>
                            <p className="text-xs text-slate-500 mb-3">이용권 구매 후 전체 결과를 확인하세요</p>
                            <PrimaryButton size="sm" onClick={() => navigate('/payment')}>
                              전체 결과 보기
                            </PrimaryButton>
                          </div>
                        )}
                      </div>
                    );
                  }

                  return <ClauseCard key={clause.id} clause={clause} />;
                })}
              </div>
            )}

            {/* 다음 단계 CTA */}
            <div className="pt-4 space-y-3">
              <div className="flex items-center gap-2 mb-2">
                <div className="flex-1 h-px bg-gray-200" />
                <p className="text-xs text-gray-400 font-medium px-2">다음 단계</p>
                <div className="flex-1 h-px bg-gray-200" />
              </div>

              <PrimaryButton
                variant="primary"
                size="md"
                fullWidth
                onClick={() => navigate(`/report/${reportId}/clauses`)}
              >
                📝 특약사항 추천 받기
              </PrimaryButton>

              <PrimaryButton
                variant="secondary"
                size="md"
                fullWidth
                onClick={() => navigate('/checklist')}
              >
                ✅ 계약 전 체크리스트 보기
              </PrimaryButton>

              <PrimaryButton
                variant="ghost"
                size="md"
                fullWidth
                onClick={() => navigate('/upload')}
              >
                새 계약서 분석하기
              </PrimaryButton>
            </div>
          </>
        )}
      </main>

      <BottomNavBar />
    </div>
  );
}
