import { useState, useEffect } from 'react';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import { analysisApi } from '../api/analysis';
import { useMarketQuery, MARKET_QUERY_LIMIT } from '../hooks/useMarketQuery';
import { formatKrw, formatNumber, formatPeriod } from '../utils/marketFormat';

// ─── 타입 ───────────────────────────────────────────────────────────────────

interface CheckItem {
  id: string;
  title: string;
  desc: string;
  link?: { href: string; label: string };
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

// ─── 컴포넌트 ─────────────────────────────────────────────────────────────────

export default function ChecklistPage() {
  const {
    isLoggedIn,
    contractMode, setContractMode,
    jeonseAmount, setJeonseAmount,
    propertyPrice, setPropertyPrice,
    sidos, selectedSido, setSelectedSido,
    selectedDistrict, setSelectedDistrict,
    dongs, selectedDong, setSelectedDong,
    dongsLoading, marketLoading,
    marketData, setMarketData,
    marketError, marketUnavailable,
    queriesRemaining, quotaExceeded,
    selectedMonths, setSelectedMonths,
    jeonseNum, ratio, isSafe, isDanger,
    districtList, handleFetchMarket,
  } = useMarketQuery();

  const [checked, setChecked] = useState<Record<string, boolean>>(loadCheckedState);
  const [modeAutoDetected, setModeAutoDetected] = useState(false);

  useEffect(() => {
    saveCheckedState(checked);
  }, [checked]);

  // 최근 계약서 유형 자동 감지
  useEffect(() => {
    if (!isLoggedIn || modeAutoDetected) return;

    analysisApi.getHistory(1, 1)
      .then(({ analyses }) => {
        const latest = analyses?.[0] as
          | { contractType?: string; contract_type?: string }
          | undefined;
        const ct = latest?.contractType ?? latest?.contract_type;
        if (ct === 'monthly') setContractMode('monthly');
        else if (ct === 'jeonse') setContractMode('jeonse');
        setModeAutoDetected(true);
      })
      .catch(() => setModeAutoDetected(true));
  }, [isLoggedIn, modeAutoDetected, setContractMode]);

  const toggle = (id: string) => {
    setChecked((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const completedCount = CHECK_ITEMS.filter((item) => checked[item.id]).length + (checked['ratio'] ? 1 : 0);
  const totalCount = CHECK_ITEMS.length + 1;
  const progressPercent = Math.round((completedCount / totalCount) * 100);

  return (
    <div className="min-h-screen bg-slate-50 pb-24">
      <NavBar title="계약 전 체크리스트" showBack />

      <main className="max-w-3xl mx-auto px-4 pt-20 pb-6 space-y-4">
        <p className="text-base font-semibold text-slate-900">계약 당일, 이것만 챙기세요.</p>

        {/* ── 체크리스트 항목들 ── */}
        {CHECK_ITEMS.map((item) => (
          <div
            key={item.id}
            className={`bg-white border rounded-xl p-4 shadow-card transition-colors ${
              checked[item.id] ? 'border-green-200 bg-green-50' : 'border-slate-200'
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
                    checked[item.id] ? 'bg-green-500 border-green-500 text-white' : 'border-slate-300'
                  }`}
                  aria-hidden="true"
                >
                  {checked[item.id] && '✓'}
                </span>
                <div className="flex-1">
                  <p className={`font-semibold ${checked[item.id] ? 'text-green-700 line-through' : 'text-slate-900'}`}>
                    {item.title}
                  </p>
                  <p className="text-sm text-slate-500 mt-1 leading-relaxed">{item.desc}</p>
                </div>
              </div>
            </button>
            {item.link && (
              <a
                href={item.link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-3 ml-9 inline-flex items-center gap-1.5 text-sm text-brand-600 hover:underline focus:outline-none focus:underline"
              >
                🔗 {item.link.label}
              </a>
            )}
          </div>
        ))}

        {/* ── 시세 확인 카드 ── */}
        <div
          className={`bg-white border rounded-xl p-4 shadow-card transition-colors ${
            checked['ratio'] ? 'border-green-200 bg-green-50' : 'border-slate-200'
          }`}
        >
          {/* 카드 헤더 */}
          <button
            className="w-full text-left mb-4 focus:outline-none"
            onClick={() => isSafe && contractMode === 'jeonse' && toggle('ratio')}
            aria-pressed={!!checked['ratio']}
          >
            <div className="flex items-start gap-3">
              <span
                className={`flex-shrink-0 w-6 h-6 rounded border-2 flex items-center justify-center mt-0.5 transition-colors ${
                  checked['ratio'] ? 'bg-green-500 border-green-500 text-white' : 'border-slate-300'
                }`}
                aria-hidden="true"
              >
                {checked['ratio'] && '✓'}
              </span>
              <p className={`font-semibold ${checked['ratio'] ? 'text-green-700 line-through' : 'text-slate-900'}`}>
                {contractMode === 'jeonse' ? '전세가율 확인하기' : '월세 시세 확인하기'}
              </p>
            </div>
          </button>

          <div className="ml-9 space-y-4">

            {/* ── 전세/월세 탭 ── */}
            <div className="flex gap-0 rounded-lg border border-slate-200 overflow-hidden">
              {(['jeonse', 'monthly'] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => setContractMode(mode)}
                  className={`flex-1 py-2 text-sm font-semibold transition-colors ${
                    contractMode === mode
                      ? 'bg-brand-600 text-white'
                      : 'bg-white text-slate-500 hover:bg-slate-50'
                  }`}
                >
                  {mode === 'jeonse' ? '🏠 전세' : '💳 월세'}
                </button>
              ))}
            </div>

            {modeAutoDetected && (
              <p className="text-xs text-brand-500">
                최근 분석한 계약서 기준으로 자동 선택됐어요. 탭을 눌러 변경할 수 있어요.
              </p>
            )}

            {/* ── 집계 기간 선택 ── */}
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-500 shrink-0">집계 기간</span>
              <div className="flex gap-1">
                {([1, 3, 6] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setSelectedMonths(m)}
                    className={`px-3 py-1 text-xs font-semibold rounded-full border transition-colors ${
                      selectedMonths === m
                        ? 'bg-brand-600 text-white border-brand-600'
                        : 'bg-white text-slate-500 border-slate-300 hover:border-brand-400 hover:text-brand-600'
                    }`}
                  >
                    {m}개월
                  </button>
                ))}
              </div>
            </div>

            {/* 유형별 안내 */}
            {contractMode === 'jeonse' ? (
              <p className="text-sm text-slate-500">
                안전 기준: 전세금 ÷ 매매가 = <strong>70% 이하</strong>
              </p>
            ) : (
              <p className="text-sm text-slate-500">
                이 지역 평균 월세와 비교해 내 계약이 적정한지 확인하세요.
              </p>
            )}

            {/* ── 실거래가 조회 ── */}
            {!marketUnavailable && (
              <div className="bg-brand-50 border border-brand-100 rounded-lg p-3 space-y-2">
                <p className="text-xs font-semibold text-brand-700">
                  {contractMode === 'jeonse'
                    ? '📊 국토교통부 실거래가로 매매가 자동 채우기'
                    : '📊 국토교통부 실거래가로 월세 시세 확인'}
                </p>

                <div className="flex gap-2">
                  <select
                    value={selectedSido}
                    onChange={(e) => { setSelectedSido(e.target.value); setSelectedDistrict(''); setMarketData(null); }}
                    className="flex-1 h-9 px-2 text-sm bg-white border border-brand-200 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-600"
                    aria-label="시도 선택"
                  >
                    <option value="">시/도 선택</option>
                    {sidos.map((s) => (
                      <option key={s.code} value={s.code}>{s.name}</option>
                    ))}
                  </select>

                  <select
                    value={selectedDistrict}
                    onChange={(e) => { setSelectedDistrict(e.target.value); setSelectedDong(''); setMarketData(null); }}
                    disabled={!selectedSido}
                    className="flex-1 h-9 px-2 text-sm bg-white border border-brand-200 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-600 disabled:opacity-50"
                    aria-label="시군구 선택"
                  >
                    <option value="">구/군/시 선택</option>
                    {districtList.map((d) => (
                      <option key={d.code} value={d.code}>{d.name}</option>
                    ))}
                  </select>
                </div>

                {(dongs.length > 0 || dongsLoading) && (
                  <select
                    value={selectedDong}
                    onChange={(e) => { setSelectedDong(e.target.value); setMarketData(null); }}
                    disabled={dongsLoading}
                    className="w-full h-9 px-2 text-sm bg-white border border-brand-200 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-600 disabled:opacity-50"
                    aria-label="법정동 선택"
                  >
                    <option value="">{dongsLoading ? '동 목록 로드 중...' : '전체 동 평균'}</option>
                    {dongs.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                )}

                {quotaExceeded ? (
                  <div className="bg-amber-50 border border-amber-200 rounded-md p-3 text-center">
                    <p className="text-xs font-semibold text-amber-700 mb-1">
                      🔒 무료 시세 조회 {MARKET_QUERY_LIMIT}회를 모두 사용했어요
                    </p>
                    <p className="text-xs text-amber-600 mb-2">이용권 구매 후 계속 조회할 수 있어요.</p>
                    <a
                      href="/payment"
                      className="inline-block px-4 py-1.5 bg-amber-500 text-white text-xs font-semibold rounded-md hover:bg-amber-600 transition-colors"
                    >
                      이용권 구매하기
                    </a>
                  </div>
                ) : (
                  <>
                    <div className="flex items-center justify-between">
                      <button
                        onClick={handleFetchMarket}
                        disabled={!selectedDistrict || marketLoading || !isLoggedIn}
                        className="flex-1 h-9 bg-brand-600 text-white text-sm font-medium rounded-md disabled:opacity-50 hover:bg-brand-700 transition-colors focus:outline-none focus:ring-2 focus:ring-brand-600"
                      >
                        {marketLoading ? '조회 중...' : !isLoggedIn ? '로그인 후 조회 가능' : '실거래가 조회'}
                      </button>
                      {isLoggedIn && queriesRemaining !== null && (
                        <span className="ml-2 text-xs text-slate-400 whitespace-nowrap">
                          {queriesRemaining === -1
                            ? '조회 ∞ (개발 무제한)'
                            : `남은 조회 ${queriesRemaining}/${MARKET_QUERY_LIMIT}회`}
                        </span>
                      )}
                    </div>
                    {!isLoggedIn && (
                      <p className="text-xs text-slate-500 text-center">
                        <a href="/login" className="text-brand-600 hover:underline">로그인</a>하면 무료 3회 시세 조회를 이용할 수 있어요.
                      </p>
                    )}
                  </>
                )}

                {marketError && <p className="text-xs text-red-600">{marketError}</p>}

                {/* ── 조회 결과: 전세 ── */}
                {marketData && contractMode === 'jeonse' && (
                  <div className="bg-white rounded-md p-2 border border-brand-100 space-y-1">
                    <p className="text-xs font-semibold text-slate-700">
                      {marketData.district_name ?? marketData.district_code}
                      {' · '}
                      {formatPeriod(marketData.period_from, marketData.period_to, marketData.deal_ym)}
                    </p>

                    {marketData.trade.count > 0 ? (
                      <p className="text-xs text-slate-600">
                        🏠 매매 평균 <strong>{formatKrw(marketData.trade.avg_price_krw)}</strong>
                        <span className="text-slate-400 ml-1">
                          ({marketData.trade.count}건, {formatKrw(marketData.trade.min_price_krw)}~{formatKrw(marketData.trade.max_price_krw)})
                        </span>
                      </p>
                    ) : (
                      <p className="text-xs text-slate-400">해당 기간 매매 거래 없음</p>
                    )}

                    {marketData.rent && marketData.rent.count > 0 ? (
                      <p className="text-xs text-slate-600">
                        🔑 전세 평균 <strong>{formatKrw(marketData.rent.avg_deposit_krw)}</strong>
                        <span className="text-slate-400 ml-1">({marketData.rent.count}건)</span>
                      </p>
                    ) : marketData.rent === null ? null : (
                      <p className="text-xs text-slate-400">해당 기간 전세 거래 없음</p>
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
                      <p className="text-xs text-brand-600">
                        ↑ 지역 평균 매매가를 참고값으로 넣었어요. 실제 해당 집 매매가로 수정해 주세요.
                      </p>
                    )}
                    <p className="text-xs text-slate-400 mt-1">
                      * 구(시군구) 단위 평균이며 동·단지별 편차가 클 수 있어요. 반드시 직접 확인 후 사용하세요.
                    </p>
                  </div>
                )}

                {/* ── 조회 결과: 월세 ── */}
                {marketData && contractMode === 'monthly' && (
                  <div className="bg-white rounded-md p-2 border border-brand-100 space-y-1">
                    <p className="text-xs font-semibold text-slate-700">
                      {marketData.district_name ?? marketData.district_code}
                      {' · '}
                      {formatPeriod(marketData.period_from, marketData.period_to, marketData.deal_ym)}
                    </p>

                    {marketData.rent && marketData.rent.avg_monthly_rent_krw ? (
                      <>
                        <p className="text-xs text-slate-600">
                          💳 월세 평균 <strong>{formatKrw(marketData.rent.avg_monthly_rent_krw)}/월</strong>
                          {marketData.rent.min_monthly_rent_krw && marketData.rent.max_monthly_rent_krw && (
                            <span className="text-slate-400 ml-1">
                              ({formatKrw(marketData.rent.min_monthly_rent_krw)}~{formatKrw(marketData.rent.max_monthly_rent_krw)})
                            </span>
                          )}
                        </p>
                        <p className="text-xs text-slate-600">
                          📦 보증금 평균 <strong>{formatKrw(marketData.rent.avg_deposit_krw)}</strong>
                          <span className="text-slate-400 ml-1">({marketData.rent.count}건)</span>
                        </p>
                      </>
                    ) : (
                      <p className="text-xs text-slate-400">해당 기간 월세 거래 없음</p>
                    )}

                    <p className="text-xs text-slate-400 mt-1">
                      * 구(시군구) 단위 평균이며 동·단지별 편차가 클 수 있어요. 반드시 직접 확인 후 사용하세요.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* ── 전세: 수동 계산기 ── */}
            {contractMode === 'jeonse' && (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">내 계약 전세금</label>
                  <div className="relative">
                    <input
                      type="text"
                      inputMode="numeric"
                      value={jeonseAmount}
                      onChange={(e) => setJeonseAmount(formatNumber(e.target.value))}
                      placeholder="0"
                      className="w-full h-11 px-4 pr-8 bg-slate-100 border border-slate-200 rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent"
                      aria-label="전세금 입력"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">원</span>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">
                    {marketData?.trade.avg_price_krw
                      ? '해당 집 매매가 (지역 평균 참고값)'
                      : '해당 집 매매가 (직접 입력)'}
                    {marketData?.trade.avg_price_krw ? (
                      <span className="ml-2 text-brand-500 font-normal">(수정 가능)</span>
                    ) : null}
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      inputMode="numeric"
                      value={propertyPrice}
                      onChange={(e) => setPropertyPrice(formatNumber(e.target.value))}
                      placeholder="0"
                      className="w-full h-11 px-4 pr-8 bg-slate-100 border border-slate-200 rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent"
                      aria-label="매매가 입력"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">원</span>
                  </div>
                </div>

                {ratio > 0 && (
                  <div
                    className={`rounded-lg p-3 border ${isSafe ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}
                    role="status"
                    aria-live="polite"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <p className={`text-sm font-semibold ${isSafe ? 'text-green-700' : 'text-red-700'}`}>
                        전세가율: {ratio}%
                      </p>
                      <span className="text-sm" aria-hidden="true">{isSafe ? '✅ 안전' : '⚠️ 위험'}</span>
                    </div>
                    <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
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
            )}

            {/* ── 월세: 내 월세 비교 ── */}
            {contractMode === 'monthly' && marketData?.rent?.avg_monthly_rent_krw && (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">내 계약 월세</label>
                  <div className="relative">
                    <input
                      type="text"
                      inputMode="numeric"
                      value={jeonseAmount}
                      onChange={(e) => setJeonseAmount(formatNumber(e.target.value))}
                      placeholder="0"
                      className="w-full h-11 px-4 pr-8 bg-slate-100 border border-slate-200 rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-brand-600 focus:border-transparent"
                      aria-label="월세 입력"
                    />
                    <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm">원/월</span>
                  </div>
                </div>

                {jeonseNum > 0 && (() => {
                  const avg = marketData.rent!.avg_monthly_rent_krw!;
                  const diff = jeonseNum - avg;
                  const pct = Math.round((diff / avg) * 100);
                  const isOverpriced = diff > avg * 0.1;
                  const isFair = Math.abs(diff) <= avg * 0.1;
                  return (
                    <div className={`rounded-lg p-3 border ${
                      isFair ? 'bg-green-50 border-green-200' : isOverpriced ? 'bg-red-50 border-red-200' : 'bg-brand-50 border-brand-200'
                    }`}>
                      <p className={`text-sm font-semibold ${
                        isFair ? 'text-green-700' : isOverpriced ? 'text-red-700' : 'text-brand-700'
                      }`}>
                        지역 평균 대비 {diff > 0 ? `+${pct}%` : `${pct}%`}
                        {' '}{isFair ? '✅ 적정' : isOverpriced ? '⚠️ 높음' : '👍 저렴'}
                      </p>
                      <p className="text-xs text-slate-500 mt-1">
                        지역 평균 {formatKrw(avg)}/월 · 내 월세 {formatKrw(jeonseNum)}/월
                      </p>
                    </div>
                  );
                })()}
              </div>
            )}

          </div>
        </div>

        {/* ── 진행 상태 ── */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-card">
          <div className="flex items-center justify-between mb-3">
            <p className="text-sm font-semibold text-slate-700">완료: {completedCount}/{totalCount} 항목</p>
            <p className="text-sm font-bold text-brand-600">{progressPercent}%</p>
          </div>
          <div className="w-full bg-slate-200 rounded-full h-3 overflow-hidden">
            <div
              className="bg-brand-600 h-3 rounded-full transition-all duration-500"
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
