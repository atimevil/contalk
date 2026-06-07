import { useNavigate } from 'react-router-dom';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import PrimaryButton from '../components/PrimaryButton';
import { useAuth } from '../context/AuthContext';

const FEATURES = [
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.623 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z" />
      </svg>
    ),
    title: '위험 조항 자동 탐지',
    desc: 'AI가 불리한 조항을 찾아 법적 근거와 함께 설명합니다',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    title: '60초 이내 분석 완료',
    desc: '계약서 업로드 즉시 OCR + AI 분석이 자동으로 시작됩니다',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
      </svg>
    ),
    title: '관련 법령 근거 제공',
    desc: '주택임대차보호법 등 법령 데이터베이스 기반 검색 결과를 제시합니다',
  },
  {
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    ),
    title: '특약사항 자동 생성',
    desc: '위험 조항에 대한 보호 특약 초안을 AI가 작성해드립니다',
  },
];

const STATS = [
  { value: '법령 DB', label: '특화 AI 모델' },
  { value: '3단계', label: '위험도 분석' },
  { value: '~30초', label: '평균 분석 시간' },
];

export default function HomePage() {
  const navigate = useNavigate();
  const { isLoggedIn, quota, isLoading } = useAuth();

  // 비로그인 또는 free_trial/none만 말풍선 표시 (로딩 중에는 숨김)
  const showFreeBubble = !isLoading && (!isLoggedIn || !quota || quota.type === 'none' || quota.type === 'free_trial');

  return (
    <div className="min-h-screen bg-slate-50 pb-20">
      <NavBar />

      <main className="max-w-3xl mx-auto px-4 pt-16">
        {/* Hero Section */}
        <section className="pt-8 pb-10 text-center">
          <div className="inline-flex items-center gap-2 bg-brand-50 text-brand-600 text-xs font-bold px-3 py-1.5 rounded-full mb-5 border border-brand-200">
            <span className="w-1.5 h-1.5 bg-accent-500 rounded-full animate-pulse" />
            AI 기반 임대차 계약서 분석 서비스
          </div>

          <h1 className="text-4xl sm:text-5xl font-extrabold text-slate-900 leading-[1.2] mb-4 text-balance tracking-tight">
            계약서의 위험,<br />
            서명 전에 확인하세요.
          </h1>
          <p className="text-lg text-slate-500 mb-8 leading-relaxed max-w-lg mx-auto">
            법령특화 AI 모델과 법령 데이터베이스로<br className="hidden sm:block" />
            임대차 계약서의 불리한 조항을 자동으로 탐지합니다.
          </p>

          <div className="flex flex-col items-center gap-3 max-w-sm mx-auto mt-2">
            {/* 말풍선 — 비로그인 또는 무료 유저만 표시 */}
            {showFreeBubble && (
              <div className="relative mb-1">
                <span className="bg-slate-800 text-white text-xs font-bold px-3 py-1.5 rounded-full shadow-md">
                  1회 무료 체험 가능
                </span>
                <span className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-2.5 h-2.5 bg-slate-800 rotate-45" />
              </div>
            )}

            <PrimaryButton
              size="lg"
              fullWidth
              onClick={() => navigate('/upload')}
            >
              계약서 분석 시작
            </PrimaryButton>
            <PrimaryButton
              size="lg"
              fullWidth
              variant="secondary"
              onClick={() => navigate('/market')}
            >
              전세가율 조회
            </PrimaryButton>
          </div>

          <p className="text-xs text-slate-400 mt-4">
            전체 결과 열람 2,900원 · 월정액 무제한 9,900원
          </p>
        </section>

        {/* 수치 */}
        <section className="py-6">
          <div className="grid grid-cols-3 gap-4">
            {STATS.map((stat) => (
              <div key={stat.label} className="text-center py-4 bg-white rounded-xl border border-slate-200 shadow-card">
                <p className="text-2xl font-extrabold text-brand-600">{stat.value}</p>
                <p className="text-xs text-slate-500 mt-1 font-medium">{stat.label}</p>
              </div>
            ))}
          </div>
        </section>

        {/* 서비스 특징 */}
        <section className="py-8">
          <h2 className="section-title text-center mb-6">주요 기능</h2>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {FEATURES.map((feature) => (
              <div
                key={feature.title}
                className="card-hover flex gap-4 items-start"
              >
                <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-100">
                  {feature.icon}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-slate-900">{feature.title}</p>
                  <p className="text-xs text-slate-500 mt-1 leading-relaxed">{feature.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 분석 프로세스 */}
        <section className="py-8">
          <h2 className="section-title text-center mb-6">분석 프로세스</h2>
          <div className="flex flex-col sm:flex-row items-stretch gap-3">
            {[
              { step: '01', title: '업로드', desc: 'PDF·사진 업로드' },
              { step: '02', title: 'OCR + 파싱', desc: '텍스트 추출·조항 분리' },
              { step: '03', title: 'AI 분석', desc: '위험도 분류·법령 검색' },
              { step: '04', title: '리포트', desc: '조항별 상세 결과 확인' },
            ].map((item, i) => (
              <div key={item.step} className="flex-1 relative">
                <div className="card text-center py-5">
                  <span className="text-xs font-bold text-brand-600 tracking-widest">{item.step}</span>
                  <p className="text-sm font-bold text-slate-900 mt-1">{item.title}</p>
                  <p className="text-xs text-slate-500 mt-0.5">{item.desc}</p>
                </div>
                {i < 3 && (
                  <div className="hidden sm:block absolute top-1/2 -right-2 text-slate-300 text-lg z-10">→</div>
                )}
              </div>
            ))}
          </div>
        </section>

        {/* 프로세스 이후 여백 */}
      </main>

      <BottomNavBar />
    </div>
  );
}
