import { useState, useEffect, useCallback } from 'react';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';

// ─── 타입 ───────────────────────────────────────────────────────────────────

interface CheckItem {
  id: string;
  title: string;
  desc: string;
  link?: { href: string; label: string };
}

interface DistrictItem {
  name: string;
  code: string;
}

interface SidoItem {
  name: string;
  code: string;
  시군구: DistrictItem[];
}

interface MarketSummary {
  district_code: string;
  district_name: string | null;
  deal_ym: string;
  trade: {
    count: number;
    avg_price_krw: number;
    min_price_krw: number;
    max_price_krw: number;
  };
  rent: {          // 전세 API 별도 승인 필요 — null일 수 있음
    count: number;
    avg_deposit_krw: number;
    min_deposit_krw: number;
    max_deposit_krw: number;
  } | null;
  jeonse_ratio_pct: number | null;
}

// ─── 상수 ────────────────────────────────────────────────────────────────────

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
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

// ─── 유틸 ────────────────────────────────────────────────────────────────────

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

function formatKrw(amount: number): string {
  if (amount >= 100_000_000) {
    const eok = Math.floor(amount / 100_000_000);
    const man = Math.round((amount % 100_000_000) / 10_000);
    return man > 0 ? `${eok}억 ${man.toLocaleString()}만원` : `${eok}억원`;
  }
  if (amount >= 10_000) {
    return `${Math.round(amount / 10_000).toLocaleString()}만원`;
  }
  return `${amount.toLocaleString()}원`;
}

function formatNumber(value: string): string {
  const num = value.replace(/[^0-9]/g, '');
  return num ? parseInt(num).toLocaleString() : '';
}

// ─── 컴포넌트 ─────────────────────────────────────────────────────────────────

export default function ChecklistPage() {
  const [checked, setChecked] = useState<Record<string, boolean>>(loadCheckedState);

  // 전세가율 계산기 — 수동 입력
  const [jeonseAmount, setJeonseAmount] = useState('');
  const [propertyPrice, setPropertyPrice] = useState('');

  // 실거래가 조회
  const [sidos, setSidos] = useState<SidoItem[]>([]);
  const [selectedSido, setSelectedSido] = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketData, setMarketData] = useState<MarketSummary | null>(null);
  const [marketError, setMarketError] = useState<string | null>(null);
  const [marketUnavailable, setMarketUnavailable] = useState(false);

  useEffect(() => {
    saveCheckedState(checked);
  }, [checked]);

  // 시도 목록 로드
  useEffect(() => {
    fetch(`${API_BASE}/api/v1/market/districts`)
      .then((r) => r.json())
      .then((data) => {
        if (data?.items) setSidos(data.items);
      })
      .catch(() => {
        // 시도 목록 로드 실패 시 조용히 무시 (기능 비활성화)
        setMarketUnavailable(true);
      });
  }, []);

  const toggle = (id: string) => {
    setChecked((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const completedCount = CHECK_ITEMS.filter((item) => checked[item.id]).length + (checked['ratio'] ? 1 : 0);
  const totalCount = CHECK_ITEMS.length + 1;
  const progressPercent = Math.round((completedCount / totalCount) * 100);

  // 전세가율 계산 (수동 입력 기준)
  const jeonseNum = parseFloat(jeonseAmount.replace(/,/g, '')) || 0;
  const propertyNum = parseFloat(propertyPrice.replace(/,/g, '')) || 0;
  const ratio = propertyNum > 0 ? Math.round((jeonseNum / propertyNum) * 100) : 0;
  const isSafe = ratio > 0 && ratio <= 70;
  const isDanger = ratio > 70;

  // 선택된 시도의 시군구 목록
  const districtList: DistrictItem[] =
    sidos.find((s) => s.code === selectedSido)?.시군구 ?? [];

  // 실거래가 조회
  const handleFetchMarket = useCallback(async () => {
    if (!selectedDistrict) return;
    setMarketLoading(true);
    setMarketError(null);
    setMarketData(null);

    try {
      const res = await fetch(
        `${API_BASE}/api/v1/market/summary?district_code=${selectedDistrict}`
      );
      if (res.status === 503) {
        setMarketError('시세 조회 서비스가 현재 설정되지 않았습니다.');
        return;
      }
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setMarketError(body?.detail?.error?.message ?? '시세 조회에 실패했습니다.');
        return;
      }
      const data: MarketSummary = await res.json();
      setMarketData(data);

      // 매매가 자동 채우기
      if (data.trade.avg_price_krw > 0) {
        setPropertyPrice(data.trade.avg_price_krw.toLocaleString());
      }
    } catch {
      setMarketError('네트워크 오류로 시세 조회에 실패했습니다.');
    } finally {
      setMarketLoading(false);
    }
  }, [selectedDistrict]);

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar title="계약 전 체크리스트" showBack />

      <main className="max-w-2xl mx-auto px-4 pt-20 pb-6 space-y-4">
        <p className="text-base font-semibold text-gray-900">계약 당일, 이것만 챙기세요.</p>

        {/* ── 체크리스트 항목들 ── */}
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

        {/* ── 전세가율 확인 카드 ── */}
        <div
          className={`bg-white border rounded-xl p-4 shadow-card transition-colors ${
            checked['ratio'] ? 'border-green-200 bg-green-50' : 'border-gray-200'
          }`}
        >
          {/* 카드 헤더 — 체크박스 */}
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

          <div className="ml-9 space-y-4">
            <p className="text-sm text-gray-500">
              안전 기준: 전세금 ÷ 매매가 = <strong>70% 이하</strong>
            </p>

            {/* ── 실거래가 조회 (MOLIT API) ── */}
            {!marketUnavailable && (
              <div className="bg-blue-50 border border-blue-100 rounded-lg p-3 space-y-2">
                <p className="text-xs font-semibold text-blue-700">
                  📊 국토교통부 실거래가로 매매가 자동 채우기
                </p>

                <div className="flex gap-2">
                  {/* 시도 선택 */}
                  <select
                    value={selectedSido}
                    onChange={(e) => {
                      setSelectedSido(e.target.value);
                      setSelectedDistrict('');
                      setMarketData(null);
                    }}
                    className="flex-1 h-9 px-2 text-sm bg-white border border-blue-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400"
                    aria-label="시도 선택"
                  >
                    <option value="">시/도 선택</option>
                    {sidos.map((s) => (
                      <option key={s.code} value={s.code}>
                        {s.name}
                      </option>
                    ))}
                  </select>

                  {/* 시군구 선택 */}
                  <select
                    value={selectedDistrict}
                    onChange={(e) => {
                      setSelectedDistrict(e.target.value);
                      setMarketData(null);
                    }}
                    disabled={!selectedSido}
                    className="flex-1 h-9 px-2 text-sm bg-white border border-blue-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-400 disabled:opacity-50"
                    aria-label="시군구 선택"
                  >
                    <option value="">구/군/시 선택</option>
                    {districtList.map((d) => (
                      <option key={d.code} value={d.code}>
                        {d.name}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  onClick={handleFetchMarket}
                  disabled={!selectedDistrict || marketLoading}
                  className="w-full h-9 bg-blue-600 text-white text-sm font-medium rounded-md disabled:opacity-50 hover:bg-blue-700 transition-colors focus:outline-none focus:ring-2 focus:ring-blue-400"
                >
                  {marketLoading ? '조회 중...' : '실거래가 조회'}
                </button>

                {/* 오류 메시지 */}
                {marketError && (
                  <p className="text-xs text-red-600">{marketError}</p>
                )}

                {/* 조회 결과 요약 */}
                {marketData && (
                  <div className="bg-white rounded-md p-2 border border-blue-100 space-y-1">
                    <p className="text-xs font-semibold text-gray-700">
                      {marketData.district_name ?? marketData.district_code} · {marketData.deal_ym.slice(0, 4)}년 {marketData.deal_ym.slice(4)}월
                    </p>

                    {marketData.trade.count > 0 ? (
                      <p className="text-xs text-gray-600">
                        🏠 매매 평균 <strong>{formatKrw(marketData.trade.avg_price_krw)}</strong>
                        <span className="text-gray-400 ml-1">
                          ({marketData.trade.count}건, {formatKrw(marketData.trade.min_price_krw)}~{formatKrw(marketData.trade.max_price_krw)})
                        </span>
                      </p>
                    ) : (
                      <p className="text-xs text-gray-400">해당 기간 매매 거래 없음</p>
                    )}

                    {marketData.rent.count > 0 ? (
                      <p className="text-xs text-gray-600">
                        🔑 전세 평균 <strong>{formatKrw(marketData.rent.avg_deposit_krw)}</strong>
                        <span className="text-gray-400 ml-1">
                          ({marketData.rent.count}건)
                        </span>
                      </p>
                    ) : (
                      <p className="text-xs text-gray-400">해당 기간 전세 거래 없음</p>
                    )}

                    {marketData.jeonse_ratio_pct !== null && (
                      <p className={`text-xs font-semibold mt-1 ${
                        marketData.jeonse_ratio_pct <= 70 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        지역 평균 전세가율: {marketData.jeonse_ratio_pct}%{' '}
                        {marketData.jeonse_ratio_pct <= 70 ? '✅' : '⚠️'}
                      </p>
                    )}

                    {marketData.trade.avg_price_krw > 0 && (
                      <p className="text-xs text-blue-600">
                        ↑ 평균 매매가를 '해당 집 매매가'에 자동으로 입력했어요.
                      </p>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── 수동 입력 계산기 ── */}
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
                  {marketData?.trade.avg_price_krw ? (
                    <span className="ml-2 text-blue-500 font-normal">
                      (실거래가 자동 입력됨)
                    </span>
                  ) : null}
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

              {/* 전세가율 계산 결과 */}
              {ratio > 0 && (
                <div
                  className={`rounded-lg p-3 border ${
                    isSafe ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
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

        {/* ── 진행 상태 ── */}
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
