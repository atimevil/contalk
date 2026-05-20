import { useState, useEffect } from 'react';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';

interface CheckItem {
  id: string;
  title: string;
  desc: string;
  link?: { href: string; label: string };
}

const CHECK_ITEMS: CheckItem[] = [
  {
    id: 'confirmed-date',
    title: '확정일자 받기',
    desc: '계약 당일 주민센터 방문 또는 인터넷등기소에서 온라인 신청. 보증금 보호의 기본!',
    link: { href: 'https://www.iros.go.kr', label: '인터넷등기소 바로가기' },
  },
  {
    id: 'move-in',
    title: '전입신고 하기',
    desc: '이사 후 14일 이내 동사무소 또는 정부24에서 신청. 신고 안하면 대항력 없어요!',
    link: { href: 'https://www.gov.kr', label: '정부24 바로가기' },
  },
  {
    id: 'registry',
    title: '등기부등본 확인',
    desc: '계약 직전 발급, 근저당·가압류 여부 확인 필수.',
    link: { href: 'https://www.iros.go.kr', label: '대법원 인터넷등기 바로가기' },
  },
];

const STORAGE_KEY = 'checklist-state';

function loadCheckedState(): Record<string, boolean> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : {};
  } catch {
    return {};
  }
}

function saveCheckedState(state: Record<string, boolean>) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

export default function ChecklistPage() {
  const [checked, setChecked] = useState<Record<string, boolean>>(loadCheckedState);
  const [jeonseAmount, setJeonseAmount] = useState('');
  const [propertyPrice, setPropertyPrice] = useState('');

  useEffect(() => {
    saveCheckedState(checked);
  }, [checked]);

  const toggle = (id: string) => {
    setChecked((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const completedCount = CHECK_ITEMS.filter((item) => checked[item.id]).length + (checked['ratio'] ? 1 : 0);
  const totalCount = CHECK_ITEMS.length + 1;
  const progressPercent = Math.round((completedCount / totalCount) * 100);

  // 전세가율 계산
  const jeonseNum = parseFloat(jeonseAmount.replace(/,/g, '')) || 0;
  const propertyNum = parseFloat(propertyPrice.replace(/,/g, '')) || 0;
  const ratio = propertyNum > 0 ? Math.round((jeonseNum / propertyNum) * 100) : 0;
  const isSafe = ratio > 0 && ratio <= 70;
  const isDanger = ratio > 70;

  const formatNumber = (value: string) => {
    const num = value.replace(/[^0-9]/g, '');
    return num ? parseInt(num).toLocaleString() : '';
  };

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar title="계약 전 체크리스트" showBack />

      <main className="max-w-2xl mx-auto px-4 pt-20 pb-6 space-y-4">
        <p className="text-base font-semibold text-gray-900">계약 당일, 이것만 챙기세요.</p>

        {/* 체크리스트 항목들 */}
        {CHECK_ITEMS.map((item) => (
          <div
            key={item.id}
            className={`bg-white border rounded-xl p-4 shadow-card transition-colors ${
              checked[item.id] ? 'border-green-200 bg-green-50' : 'border-gray-200'
            }`}
          >
            <button
              className="w-full text-left focus:outline-none"
              onClick={() => toggle(item.id)}
              aria-pressed={!!checked[item.id]}
            >
              <div className="flex items-start gap-3">
                <span
                  className={`flex-shrink-0 w-6 h-6 rounded border-2 flex items-center justify-center mt-0.5 transition-colors ${
                    checked[item.id]
                      ? 'bg-green-500 border-green-500 text-white'
                      : 'border-gray-300'
                  }`}
                  aria-hidden="true"
                >
                  {checked[item.id] && '✓'}
                </span>
                <div className="flex-1">
                  <p className={`font-semibold ${checked[item.id] ? 'text-green-700 line-through' : 'text-gray-900'}`}>
                    {item.title}
                  </p>
                  <p className="text-sm text-gray-500 mt-1 leading-relaxed">{item.desc}</p>
                </div>
              </div>
            </button>

            {item.link && (
              <a
                href={item.link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 ml-9 inline-flex items-center gap-1.5 text-sm text-blue-600 hover:underline focus:outline-none focus:underline"
              >
                🔗 {item.link.label}
              </a>
            )}
          </div>
        ))}

        {/* 전세가율 계산기 */}
        <div
          className={`bg-white border rounded-xl p-4 shadow-card transition-colors ${
            checked['ratio'] ? 'border-green-200 bg-green-50' : 'border-gray-200'
          }`}
        >
          <button
            className="w-full text-left mb-4 focus:outline-none"
            onClick={() => isSafe && toggle('ratio')}
            aria-pressed={!!checked['ratio']}
          >
            <div className="flex items-start gap-3">
              <span
                className={`flex-shrink-0 w-6 h-6 rounded border-2 flex items-center justify-center mt-0.5 transition-colors ${
                  checked['ratio']
                    ? 'bg-green-500 border-green-500 text-white'
                    : 'border-gray-300'
                }`}
                aria-hidden="true"
              >
                {checked['ratio'] && '✓'}
              </span>
              <p className={`font-semibold ${checked['ratio'] ? 'text-green-700 line-through' : 'text-gray-900'}`}>
                전세가율 확인하기
              </p>
            </div>
          </button>

          <div className="ml-9">
            <p className="text-sm text-gray-500 mb-3">
              안전 기준: 전세금 ÷ 매매가 = <strong>70% 이하</strong>
            </p>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  내 계약 전세금
                </label>
                <div className="relative">
                  <input
                    type="text"
                    inputMode="numeric"
                    value={jeonseAmount}
                    onChange={(e) => setJeonseAmount(formatNumber(e.target.value))}
                    placeholder="0"
                    className="w-full h-11 px-4 pr-8 bg-gray-100 border border-gray-200 rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    aria-label="전세금 입력"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">원</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">
                  해당 집 매매가
                </label>
                <div className="relative">
                  <input
                    type="text"
                    inputMode="numeric"
                    value={propertyPrice}
                    onChange={(e) => setPropertyPrice(formatNumber(e.target.value))}
                    placeholder="0"
                    className="w-full h-11 px-4 pr-8 bg-gray-100 border border-gray-200 rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    aria-label="매매가 입력"
                  />
                  <span className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">원</span>
                </div>
              </div>

              {ratio > 0 && (
                <div
                  className={`rounded-lg p-3 border ${
                    isSafe
                      ? 'bg-green-50 border-green-200'
                      : 'bg-red-50 border-red-200'
                  }`}
                  role="status"
                  aria-live="polite"
                >
                  <div className="flex items-center justify-between mb-2">
                    <p className={`text-sm font-semibold ${isSafe ? 'text-green-700' : 'text-red-700'}`}>
                      전세가율: {ratio}%
                    </p>
                    <span className="text-sm" aria-hidden="true">
                      {isSafe ? '✅ 안전' : '⚠️ 위험'}
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${
                        isSafe ? 'bg-green-500' : isDanger ? 'bg-red-500' : 'bg-yellow-500'
                      }`}
                      style={{ width: `${Math.min(ratio, 100)}%` }}
                    />
                  </div>
                  {isSafe ? (
                    <p className="text-xs text-green-700 mt-1">안전 범위입니다 ✅</p>
                  ) : (
                    <p className="text-xs text-red-700 mt-1">⚠️ 70%를 초과했어요. 신중하게 검토하세요.</p>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* 진행 상태 */}
        <div className="bg-white border border-gray-200 rounded-xl p-4 shadow-card">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-semibold text-gray-700">완료: {completedCount}/{totalCount} 항목</p>
            <p className="text-sm font-bold text-blue-600">{progressPercent}%</p>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-3 overflow-hidden">
            <div
              className="bg-blue-600 h-3 rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
              role="progressbar"
              aria-valuenow={progressPercent}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label={`체크리스트 진행률 ${progressPercent}%`}
            />
          </div>
          {completedCount === totalCount && (
            <p className="text-sm text-green-600 font-medium mt-2 text-center">
              모든 항목을 완료했어요! 🎉
            </p>
          )}
        </div>
      </main>

      <BottomNavBar />
    </div>
  );
}
