import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { marketApi } from '../api/market';
import type { MarketSummaryResponse, SidoItem, DistrictItem } from '../types/api';

export type ContractMode = 'jeonse' | 'monthly';

/** 무료 시세 조회 허용 횟수 */
export const MARKET_QUERY_LIMIT = 3;

/**
 * 실거래가/전세가율 시세 조회 상태와 로직을 캡슐화한 공용 훅.
 *
 * MarketPage와 ChecklistPage에 동일하게 중복되어 있던
 * (지역 선택 → 동 목록 로드 → summary 조회 → 전세가율 계산) 흐름을
 * 단일 출처로 통합한다. 페이지는 반환값을 구조분해해 기존 JSX 그대로 사용한다.
 */
export function useMarketQuery() {
  const { isLoggedIn } = useAuth();

  const [contractMode, setContractMode] = useState<ContractMode>('jeonse');
  const [jeonseAmount, setJeonseAmount] = useState('');
  const [propertyPrice, setPropertyPrice] = useState('');

  const [sidos, setSidos] = useState<SidoItem[]>([]);
  const [selectedSido, setSelectedSido] = useState('');
  const [selectedDistrict, setSelectedDistrict] = useState('');
  const [dongs, setDongs] = useState<string[]>([]);
  const [selectedDong, setSelectedDong] = useState('');
  const [dongsLoading, setDongsLoading] = useState(false);
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketData, setMarketData] = useState<MarketSummaryResponse | null>(null);
  const [marketError, setMarketError] = useState<string | null>(null);
  const [marketUnavailable, setMarketUnavailable] = useState(false);
  const [queriesRemaining, setQueriesRemaining] = useState<number | null>(null);
  const [quotaExceeded, setQuotaExceeded] = useState(false);
  const [selectedMonths, setSelectedMonths] = useState<1 | 3 | 6>(6);

  // 시도 목록 로드
  useEffect(() => {
    marketApi
      .districts()
      .then((res) => {
        if (res?.items?.length) setSidos(res.items);
        else setMarketUnavailable(true);
      })
      .catch(() => setMarketUnavailable(true));
  }, []);

  // 구 선택 시 동 목록 로드
  useEffect(() => {
    if (!selectedDistrict) {
      setDongs([]);
      setSelectedDong('');
      return;
    }
    setDongsLoading(true);
    marketApi
      .dongs(selectedDistrict)
      .then((res) => setDongs(res?.dongs ?? []))
      .catch(() => setDongs([]))
      .finally(() => setDongsLoading(false));
  }, [selectedDistrict]);

  // contractMode 또는 selectedMonths 바뀌면 기존 결과 초기화
  useEffect(() => {
    setMarketData(null);
    setMarketError(null);
    setJeonseAmount('');
    setPropertyPrice('');
  }, [contractMode, selectedMonths]);

  const jeonseNum = parseFloat(jeonseAmount.replace(/,/g, '')) || 0;
  const propertyNum = parseFloat(propertyPrice.replace(/,/g, '')) || 0;
  const ratio = propertyNum > 0 ? Math.round((jeonseNum / propertyNum) * 100) : 0;
  const isSafe = ratio > 0 && ratio <= 70;
  const isDanger = ratio > 70;

  const districtList: DistrictItem[] =
    sidos.find((s) => s.code === selectedSido)?.시군구 ?? [];

  const handleFetchMarket = useCallback(async () => {
    if (!selectedDistrict) return;
    if (!isLoggedIn) {
      setMarketError('로그인 후 이용할 수 있습니다.');
      return;
    }
    setMarketLoading(true);
    setMarketError(null);
    setMarketData(null);
    setQuotaExceeded(false);

    try {
      const data = await marketApi.summary({
        district_code: selectedDistrict,
        dong: selectedDong || undefined,
        rent_type: contractMode,
        months: selectedMonths,
      });
      setMarketData(data);

      if (typeof data?.market_queries_remaining === 'number') {
        setQueriesRemaining(data.market_queries_remaining);
      }

      // 전세 모드: 지역 매매가 자동 채우기
      if (contractMode === 'jeonse' && data?.trade?.avg_price_krw > 0) {
        setPropertyPrice(data.trade.avg_price_krw.toLocaleString());
      }
    } catch (err) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 402) {
        setQuotaExceeded(true);
        setQueriesRemaining(0);
      } else if (status === 503) {
        setMarketError('시세 조회 서비스가 현재 설정되지 않았습니다.');
      } else if (status === 401) {
        setMarketError('로그인 세션이 만료되었습니다. 다시 로그인해 주세요.');
      } else {
        const msg = (err as {
          response?: { data?: { detail?: { error?: { message?: string } } } };
        })?.response?.data?.detail?.error?.message;
        setMarketError(msg ?? '시세 조회에 실패했습니다.');
      }
    } finally {
      setMarketLoading(false);
    }
  }, [selectedDistrict, selectedDong, isLoggedIn, contractMode, selectedMonths]);

  return {
    isLoggedIn,
    contractMode,
    setContractMode,
    jeonseAmount,
    setJeonseAmount,
    propertyPrice,
    setPropertyPrice,
    sidos,
    selectedSido,
    setSelectedSido,
    selectedDistrict,
    setSelectedDistrict,
    dongs,
    selectedDong,
    setSelectedDong,
    dongsLoading,
    marketLoading,
    marketData,
    setMarketData,
    marketError,
    marketUnavailable,
    queriesRemaining,
    quotaExceeded,
    selectedMonths,
    setSelectedMonths,
    jeonseNum,
    propertyNum,
    ratio,
    isSafe,
    isDanger,
    districtList,
    handleFetchMarket,
  };
}
