import { useNavigate } from 'react-router-dom';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import PrimaryButton from '../components/PrimaryButton';


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

      <main className="max-w-2xl mx-auto px-4 pt-16">
        {/* Hero Section */}
        <section className="pt-4 pb-3 text-center">
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

          <p className="text-xs text-gray-400 mt-2.5">무료 체험 가능 · 회원가입 후 결제</p>
        </section>

        {/* 서비스 특징 */}
        <section className="pt-4 pb-6">
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

      </main>

      <BottomNavBar />
    </div>
  );
}
