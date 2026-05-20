import { useNavigate } from 'react-router-dom';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import PrimaryButton from '../components/PrimaryButton';

const REVIEWS = [
  { id: 1, stars: 5, quote: '전세 계약 전에 꼭 써봐야 해요', author: '박모씨, 25세' },
  { id: 2, stars: 5, quote: '고위험 조항을 바로 찾아줘요', author: '이모씨, 28세' },
  { id: 3, stars: 5, quote: '법률 용어를 쉽게 풀어줘서 이해하기 쉬웠어요', author: '김모씨, 32세' },
];

const FEATURES = [
  {
    icon: '🔍',
    title: '위험 조항 자동 탐지',
    desc: '법률 용어를 쉽게 풀어드려요',
  },
  {
    icon: '⏱',
    title: '1분 이내 결과',
    desc: '업로드 후 바로 확인하세요',
  },
  {
    icon: '💰',
    title: '건당 2,900원',
    desc: '변호사 상담비의 1/100',
  },
];

export default function HomePage() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-gray-50 pb-20">
      <NavBar />

      <main className="max-w-2xl mx-auto px-4 pt-20">
        {/* Hero Section */}
        <section className="py-10 text-center">
          <h1 className="text-3xl font-bold text-gray-900 leading-tight mb-3 text-balance">
            계약서, 혼자 읽다가<br />
            손해보지 마세요.
          </h1>
          <p className="text-base text-gray-500 mb-8 leading-relaxed">
            AI가 위험 조항을 찾아<br />
            쉬운 말로 설명해드려요.
          </p>

          <PrimaryButton
            size="lg"
            fullWidth
            onClick={() => navigate('/upload')}
            className="max-w-sm mx-auto"
          >
            📄 내 계약서 분석하기
          </PrimaryButton>

          <p className="text-xs text-gray-400 mt-3">무료 체험 가능 · 회원가입 후 결제</p>
        </section>

        {/* 후기 섹션 */}
        <section className="py-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex-1 h-px bg-gray-200" />
            <p className="text-sm text-gray-500 font-medium px-2">실제 사용자 후기</p>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          <div className="flex gap-3 overflow-x-auto scroll-hidden -mx-4 px-4 pb-2">
            {REVIEWS.map((review) => (
              <div
                key={review.id}
                className="flex-shrink-0 w-52 bg-white border border-gray-200 rounded-xl p-4 shadow-card"
              >
                <div className="text-yellow-400 text-sm mb-2" aria-label={`별점 ${review.stars}개`}>
                  {'⭐'.repeat(review.stars)}
                </div>
                <p className="text-sm text-gray-800 font-medium mb-2 leading-snug">
                  "{review.quote}"
                </p>
                <p className="text-xs text-gray-400">— {review.author}</p>
              </div>
            ))}
          </div>
        </section>

        {/* 서비스 특징 */}
        <section className="py-6">
          <div className="flex items-center gap-2 mb-4">
            <div className="flex-1 h-px bg-gray-200" />
            <p className="text-sm text-gray-500 font-medium px-2">서비스 특징</p>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          <div className="space-y-3">
            {FEATURES.map((feature) => (
              <div
                key={feature.title}
                className="bg-white border border-gray-200 rounded-xl p-4 flex items-center gap-4 shadow-card"
              >
                <span className="text-2xl flex-shrink-0" aria-hidden="true">
                  {feature.icon}
                </span>
                <div>
                  <p className="text-base font-semibold text-gray-900">{feature.title}</p>
                  <p className="text-sm text-gray-500">{feature.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* 하단 CTA */}
        <section className="py-6 pb-4">
          <PrimaryButton
            size="lg"
            fullWidth
            onClick={() => navigate('/upload')}
          >
            지금 바로 시작하기 →
          </PrimaryButton>
          <p className="text-center text-xs text-gray-400 mt-3">
            계약 체결 전 꼭 확인하세요
          </p>
        </section>
      </main>

      <BottomNavBar />
    </div>
  );
}
