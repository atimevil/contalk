import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import PrimaryButton from '../components/PrimaryButton';
import SkeletonLoader from '../components/SkeletonLoader';
import { specialClausesApi } from '../api/specialClauses';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import type { SpecialClause } from '../types/api';

const categoryLabel: Record<string, string> = {
  renewal: '갱신',
  repair: '수선비',
  deposit: '보증금',
  entry: '전입신고',
  termination: '계약 해지',
  facility: '시설물',
  other: '기타',
};

function SpecialClauseCard({ clause }: { clause: SpecialClause }) {
  const { reportId } = useParams<{ reportId: string }>();
  const { showToast } = useToast();
  const [text, setText] = useState(clause.text);
  const [isEditing, setIsEditing] = useState(false);
  const [isCopied, setIsCopied] = useState(false);

  const updateMutation = useMutation({
    mutationFn: (newText: string) =>
      specialClausesApi.update(reportId!, clause.id, { text: newText }),
    onSuccess: (data) => {
      setText(data.text);
      setIsEditing(false);
      showToast({ type: 'success', message: '특약 문구가 저장되었어요.' });
    },
    onError: () => {
      showToast({ type: 'error', message: '저장에 실패했어요.' });
    },
  });

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setIsCopied(true);
      showToast({ type: 'success', message: '복사되었어요!' });
      setTimeout(() => setIsCopied(false), 2000);
    } catch {
      showToast({ type: 'error', message: '복사에 실패했어요.' });
    }
  };

  const riskBorderMap = {
    high: 'border-red-200',
    medium: 'border-orange-200',
    caution: 'border-amber-200',
  };

  return (
    <div className={`bg-white border rounded-xl p-4 shadow-card ${riskBorderMap[clause.relatedRisk]}`}>
      <div className="flex items-center gap-2 mb-3">
        <span className="text-green-600 font-bold text-lg" aria-hidden="true">✅</span>
        <h3 className="text-base font-semibold text-slate-900">{clause.title}</h3>
        <span className="ml-auto text-xs text-slate-400 bg-slate-100 rounded px-2 py-0.5">
          {categoryLabel[clause.category] || clause.category}
        </span>
      </div>

      {isEditing ? (
        <div className="mb-3">
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full border border-brand-400 rounded-lg p-3 text-sm text-slate-800 leading-relaxed resize-none focus:outline-none focus:ring-2 focus:ring-brand-600"
            rows={6}
            maxLength={2000}
            aria-label="특약 문구 편집"
          />
          <div className="flex justify-between items-center mt-1">
            <span className="text-xs text-slate-400">{text.length}/2000자</span>
          </div>
          <div className="flex gap-2 mt-2">
            <PrimaryButton size="sm" onClick={() => updateMutation.mutate(text)} loading={updateMutation.isPending}>
              저장
            </PrimaryButton>
            <PrimaryButton
              size="sm"
              variant="ghost"
              onClick={() => {
                setText(clause.text);
                setIsEditing(false);
              }}
            >
              취소
            </PrimaryButton>
          </div>
        </div>
      ) : (
        <p className="text-sm text-slate-800 leading-relaxed bg-slate-50 rounded-lg p-3 mb-3">
          {text}
        </p>
      )}

      {!isEditing && (
        <div className="flex gap-2">
          <PrimaryButton size="sm" variant="secondary" onClick={handleCopy} className="flex-1">
            {isCopied ? '복사됨' : '복사하기'}
          </PrimaryButton>
          {clause.isEditable && (
            <PrimaryButton size="sm" variant="ghost" onClick={() => setIsEditing(true)} className="flex-1">
              수정하기
            </PrimaryButton>
          )}
        </div>
      )}
    </div>
  );
}

export default function SpecialClausesPage() {
  const { reportId } = useParams<{ reportId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { quota } = useAuth();
  const [isDownloading, setIsDownloading] = useState(false);

  const isPaidUser = quota && quota.type !== 'none' && quota.type !== 'free_trial';

  // NOTE: 훅(useQuery)은 조건부 return보다 먼저 호출해야 한다 (React Hooks 규칙).
  //       무료 유저는 enabled=false 로 네트워크 요청만 막는다.
  const { data, isLoading, isError } = useQuery({
    queryKey: ['special-clauses', reportId],
    queryFn: () => specialClausesApi.list(reportId!),
    enabled: !!reportId && !!isPaidUser,
    staleTime: 5 * 60 * 1000,
  });

  // 무료 유저면 결제 유도 화면
  if (!isPaidUser) {
    return (
      <div className="min-h-screen bg-slate-50 pb-24">
        <NavBar title="AI 특약사항 추천" showBack />
        <main className="max-w-3xl mx-auto px-4 pt-20 pb-6 flex flex-col items-center justify-center min-h-[60vh]">
          <svg className="w-16 h-16 text-brand-600 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
          </svg>
          <h2 className="text-lg font-bold text-slate-900 mb-2">유료 기능입니다</h2>
          <p className="text-sm text-slate-500 mb-6 text-center leading-relaxed">
            AI 특약사항 추천은 이용권 구매 후<br />이용하실 수 있습니다.
          </p>
          <PrimaryButton size="lg" onClick={() => navigate('/payment')}>
            이용권 구매하기
          </PrimaryButton>
        </main>
        <BottomNavBar />
      </div>
    );
  }

  const handleDownloadPdf = async () => {
    if (!reportId) return;
    setIsDownloading(true);
    try {
      const blob = await specialClausesApi.downloadPdf(reportId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `special_clauses_${reportId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      showToast({ type: 'success', message: 'PDF 다운로드를 시작해요.' });
    } catch {
      showToast({ type: 'error', message: 'PDF 다운로드에 실패했어요.' });
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 pb-24">
      <NavBar title="특약사항 추천" showBack onBack={() => navigate(-1)} />

      <main className="max-w-3xl mx-auto px-4 pt-20 pb-6 space-y-5">
        <div>
          <p className="text-base text-slate-700 leading-relaxed">
            분석된 위험 조항에 맞춰<br />
            <strong className="text-slate-900">세입자 보호 특약</strong>을 추천해드려요.
          </p>
        </div>

        {isLoading && <SkeletonLoader variant="clause-card" count={3} />}

        {isError && (
          <div className="text-center py-12">
            <p className="text-4xl mb-3" aria-hidden="true">😢</p>
            <p className="text-base text-slate-600">문구를 불러오지 못했어요.</p>
          </div>
        )}

        {data && data.clauses.length === 0 && (
          <div className="text-center py-12">
            <p className="text-4xl mb-3" aria-hidden="true">✅</p>
            <p className="text-base text-slate-600">위험 조항이 없어 추가 특약이 필요하지 않아요!</p>
          </div>
        )}

        {data && data.clauses.length > 0 && (
          <>
            <div className="space-y-4">
              {data.clauses.map((clause) => (
                <SpecialClauseCard key={clause.id} clause={clause} />
              ))}
            </div>

            {/* 전체 다운로드 */}
            <div className="bg-brand-50 border border-brand-200 rounded-xl p-5">
              <h3 className="text-base font-semibold text-slate-900 mb-2">전체 패키지</h3>
              <p className="text-sm text-slate-600 mb-4">
                위 특약 문구를 모두 포함한 특약서 초안을 다운로드하세요.
              </p>
              <PrimaryButton
                size="md"
                fullWidth
                loading={isDownloading}
                onClick={handleDownloadPdf}
              >
                특약서 전체 다운로드 (PDF)
              </PrimaryButton>
            </div>

            {/* 면책 문구 */}
            <div className="flex items-start gap-2 text-xs text-slate-400">
              <span aria-hidden="true">⚠️</span>
              <p>
                이 문구는 참고용입니다. 법적 효력은 변호사와 확인하세요. 본 서비스는 법률 조언이
                아닌 정보 제공 서비스입니다.
              </p>
            </div>
          </>
        )}
      </main>

      <BottomNavBar />
    </div>
  );
}
