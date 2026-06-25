import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import { useMarketQuery, MARKET_QUERY_LIMIT } from '../hooks/useMarketQuery';
import { formatKrw, formatNumber, formatPeriod } from '../utils/marketFormat';

export default function MarketPage() {
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

  return (
    <div className="min-h-screen bg-slate-50 pb-24">
      <NavBar title="전세가율 · 시세 조회" showBack />

      <main className="max-w-3xl mx-auto px-4 pt-20 pb-6 space-y-5">

        {/* 소개 */}
        <div className="text-center py-2">
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">
            {contractMode === 'jeonse' ? '전세가율 계산기' : '월세 시세 비교'}
          </h2>
          <p className="text-sm text-slate-500 mt-1">
            국토교통부 실거래가 기반으로 내 계약 조건을 검증합니다.
          </p>
        </div>

        {/* 전세/월세 탭 */}
        <div className="flex gap-0 rounded-lg border border-slate-200 overflow-hidden shadow-card">
          {(['jeonse', 'monthly'] as const).map((mode) => (
            <button
              key={mode}
              onClick={() => setContractMode(mode)}
              className={`flex-1 py-3 text-sm font-bold transition-colors ${
                contractMode === mode
                  ? 'bg-brand-600 text-white'
                  : 'bg-white text-slate-500 hover:bg-slate-50'
              }`}
            >
              {mode === 'jeonse' ? '전세가율 조회' : '월세 시세 조회'}
            </button>
          ))}
        </div>

        {/* 집계 기간 */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-500 font-medium">집계 기간</span>
          <div className="flex gap-1.5">
            {([1, 3, 6] as const).map((m) => (
              <button
                key={m}
                onClick={() => setSelectedMonths(m)}
                className={`px-3 py-1.5 text-xs font-bold rounded-md border transition-colors ${
                  selectedMonths === m
                    ? 'bg-brand-600 text-white border-brand-600'
                    : 'bg-white text-slate-500 border-slate-300 hover:border-brand-400 hover:text-brand-600'
                }`}
              >
                최근 {m}개월
              </button>
            ))}
          </div>
        </div>

        {/* 지역 선택 */}
        {!marketUnavailable ? (
          <div className="card space-y-3">
            <p className="text-sm font-bold text-slate-700">지역 선택</p>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={selectedSido}
                onChange={(e) => { setSelectedSido(e.target.value); setSelectedDistrict(''); setMarketData(null); }}
                className="input-base h-10 text-sm"
                aria-label="시도 선택"
              >
                <option value="">시/도 선택</option>
                {sidos.map((s) => <option key={s.code} value={s.code}>{s.name}</option>)}
              </select>
              <select
                value={selectedDistrict}
                onChange={(e) => { setSelectedDistrict(e.target.value); setSelectedDong(''); setMarketData(null); }}
                disabled={!selectedSido}
                className="input-base h-10 text-sm disabled:opacity-50"
                aria-label="시군구 선택"
              >
                <option value="">구/군/시 선택</option>
                {districtList.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
              </select>
            </div>

            {(dongs.length > 0 || dongsLoading) && (
              <select
                value={selectedDong}
                onChange={(e) => { setSelectedDong(e.target.value); setMarketData(null); }}
                disabled={dongsLoading}
                className="input-base h-10 text-sm disabled:opacity-50"
                aria-label="법정동 선택"
              >
                <option value="">{dongsLoading ? '로드 중...' : '전체 동 평균'}</option>
                {dongs.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            )}

            {quotaExceeded ? (
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-center">
                <p className="text-sm font-bold text-amber-700 mb-1">무료 조회 횟수를 초과했습니다</p>
                <p className="text-xs text-amber-600 mb-3">이용권 구매 후 무제한 조회가 가능합니다.</p>
                <a href="/payment" className="btn-primary text-xs h-9 px-4 inline-flex">이용권 구매</a>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <button
                  onClick={handleFetchMarket}
                  disabled={!selectedDistrict || marketLoading || !isLoggedIn}
                  className="btn-primary flex-1 h-10 text-sm"
                >
                  {marketLoading ? '조회 중...' : !isLoggedIn ? '로그인 후 조회 가능' : '실거래가 조회'}
                </button>
                {isLoggedIn && queriesRemaining !== null && (
                  <span className="text-xs text-slate-400 whitespace-nowrap">
                    {queriesRemaining === -1 ? '∞' : `${queriesRemaining}/${MARKET_QUERY_LIMIT}회`}
                  </span>
                )}
              </div>
            )}

            {marketError && <p className="text-xs text-red-600 font-medium">{marketError}</p>}
          </div>
        ) : (
          <div className="card text-center py-8">
            <p className="text-sm text-slate-500">시세 조회 서비스가 현재 이용 불가합니다.</p>
          </div>
        )}

        {/* 조회 결과 */}
        {marketData && (
          <div className="card border-brand-200 bg-brand-50/30 space-y-3">
            <p className="text-sm font-bold text-slate-800">
              📊 {marketData.district_name ?? marketData.district_code}
              {' · '}
              <span className="text-slate-500 font-normal">
                {formatPeriod(marketData.period_from, marketData.period_to, marketData.deal_ym)}
              </span>
            </p>

            {contractMode === 'jeonse' && (
              <>
                {marketData.trade.count > 0 && (
                  <div className="flex justify-between items-center py-2 border-b border-slate-200">
                    <span className="text-sm text-slate-600">매매 평균</span>
                    <span className="text-sm font-bold text-slate-900">{formatKrw(marketData.trade.avg_price_krw)}</span>
                  </div>
                )}
                {marketData.rent && marketData.rent.count > 0 && (
                  <div className="flex justify-between items-center py-2 border-b border-slate-200">
                    <span className="text-sm text-slate-600">전세 평균</span>
                    <span className="text-sm font-bold text-slate-900">{formatKrw(marketData.rent.avg_deposit_krw)}</span>
                  </div>
                )}
                {marketData.jeonse_ratio_pct !== null && (
                  <div className={`flex justify-between items-center py-2 rounded-md px-3 ${
                    marketData.jeonse_ratio_pct <= 70 ? 'bg-green-50' : 'bg-red-50'
                  }`}>
                    <span className="text-sm font-bold">지역 평균 전세가율</span>
                    <span className={`text-lg font-extrabold ${
                      marketData.jeonse_ratio_pct <= 70 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {marketData.jeonse_ratio_pct}%
                    </span>
                  </div>
                )}
              </>
            )}

            {contractMode === 'monthly' && marketData.rent && (
              <>
                {marketData.rent.avg_monthly_rent_krw && (
                  <div className="flex justify-between items-center py-2 border-b border-slate-200">
                    <span className="text-sm text-slate-600">월세 평균</span>
                    <span className="text-sm font-bold text-slate-900">{formatKrw(marketData.rent.avg_monthly_rent_krw)}/월</span>
                  </div>
                )}
                <div className="flex justify-between items-center py-2 border-b border-slate-200">
                  <span className="text-sm text-slate-600">보증금 평균</span>
                  <span className="text-sm font-bold text-slate-900">{formatKrw(marketData.rent.avg_deposit_krw)}</span>
                </div>
                <p className="text-xs text-slate-400">거래 {marketData.rent.count}건 기준</p>
              </>
            )}

            <p className="text-xs text-slate-400">
              * 구(시군구) 단위 통계이며 동·단지별 편차가 있을 수 있습니다.
            </p>
          </div>
        )}

        {/* 전세가율 직접 계산기 */}
        {contractMode === 'jeonse' && (
          <div className="card space-y-4">
            <p className="text-sm font-bold text-slate-700">내 계약 전세가율 계산</p>

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">전세금</label>
              <div className="relative">
                <input
                  type="text"
                  inputMode="numeric"
                  value={jeonseAmount}
                  onChange={(e) => setJeonseAmount(formatNumber(e.target.value))}
                  placeholder="0"
                  className="input-base pr-10"
                  aria-label="전세금 입력"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 text-sm">원</span>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">
                매매가
                {marketData?.trade.avg_price_krw ? (
                  <span className="ml-2 text-brand-500 font-normal">(지역 평균 참고값 · 수정 가능)</span>
                ) : null}
              </label>
              <div className="relative">
                <input
                  type="text"
                  inputMode="numeric"
                  value={propertyPrice}
                  onChange={(e) => setPropertyPrice(formatNumber(e.target.value))}
                  placeholder="0"
                  className="input-base pr-10"
                  aria-label="매매가 입력"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 text-sm">원</span>
              </div>
            </div>

            {ratio > 0 && (
              <div className={`rounded-lg p-4 border ${isSafe ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
                <div className="flex items-center justify-between mb-2">
                  <p className={`text-base font-extrabold ${isSafe ? 'text-green-700' : 'text-red-700'}`}>
                    전세가율 {ratio}%
                  </p>
                  <span className={`text-xs font-bold px-2 py-1 rounded ${isSafe ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                    {isSafe ? '안전' : '위험'}
                  </span>
                </div>
                <div className="w-full bg-slate-200 rounded-full h-2.5 overflow-hidden">
                  <div
                    className={`h-2.5 rounded-full transition-all duration-500 ${
                      isSafe ? 'bg-green-500' : isDanger ? 'bg-red-500' : 'bg-amber-500'
                    }`}
                    style={{ width: `${Math.min(ratio, 100)}%` }}
                  />
                </div>
                <p className={`text-xs mt-2 ${isSafe ? 'text-green-600' : 'text-red-600'}`}>
                  {isSafe ? '70% 이하로 안전 범위입니다.' : '70% 초과 — 깡통전세 위험이 있습니다. 신중하게 검토하세요.'}
                </p>
              </div>
            )}
          </div>
        )}

        {/* 월세 비교 */}
        {contractMode === 'monthly' && marketData?.rent?.avg_monthly_rent_krw && (
          <div className="card space-y-4">
            <p className="text-sm font-bold text-slate-700">내 월세 비교</p>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1.5">내 계약 월세</label>
              <div className="relative">
                <input
                  type="text"
                  inputMode="numeric"
                  value={jeonseAmount}
                  onChange={(e) => setJeonseAmount(formatNumber(e.target.value))}
                  placeholder="0"
                  className="input-base pr-14"
                  aria-label="월세 입력"
                />
                <span className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 text-sm">원/월</span>
              </div>
            </div>

            {jeonseNum > 0 && (() => {
              const avg = marketData.rent!.avg_monthly_rent_krw!;
              const diff = jeonseNum - avg;
              const pct = Math.round((diff / avg) * 100);
              const isOverpriced = diff > avg * 0.1;
              const isFair = Math.abs(diff) <= avg * 0.1;
              return (
                <div className={`rounded-lg p-4 border ${
                  isFair ? 'bg-green-50 border-green-200' : isOverpriced ? 'bg-red-50 border-red-200' : 'bg-blue-50 border-blue-200'
                }`}>
                  <p className={`text-base font-extrabold ${
                    isFair ? 'text-green-700' : isOverpriced ? 'text-red-700' : 'text-blue-700'
                  }`}>
                    지역 평균 대비 {diff > 0 ? `+${pct}%` : `${pct}%`}
                    <span className="ml-2 text-xs font-bold">{isFair ? '적정' : isOverpriced ? '높음' : '저렴'}</span>
                  </p>
                  <p className="text-xs text-slate-500 mt-1">
                    지역 평균 {formatKrw(avg)}/월 · 내 월세 {formatKrw(jeonseNum)}/월
                  </p>
                </div>
              );
            })()}
          </div>
        )}

      </main>

      <BottomNavBar />
    </div>
  );
}
