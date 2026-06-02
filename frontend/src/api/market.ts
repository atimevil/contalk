import apiClient from './client';
import type {
  DistrictsResponse,
  DongsResponse,
  AptTradeStat,
  AptRentStat,
  MarketSummaryResponse,
} from '../types/api';

type RentType = 'jeonse' | 'monthly';

/** 백엔드 success wrapper({ success, data }) 유무에 상관없이 본문을 추출 */
function unwrap<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data;
  }
  return body as T;
}

export const marketApi = {
  /** 시도·시군구 코드 목록 (인증 불필요) */
  districts: async (): Promise<DistrictsResponse> => {
    const res = await apiClient.get('/market/districts');
    return unwrap<DistrictsResponse>(res.data);
  },

  /** 시군구 내 법정동 목록 (인증 불필요, 24시간 캐시) */
  dongs: async (districtCode: string, dealYm?: string): Promise<DongsResponse> => {
    const res = await apiClient.get('/market/dongs', {
      params: { district_code: districtCode, deal_ym: dealYm },
    });
    return unwrap<DongsResponse>(res.data);
  },

  /** 아파트 매매 실거래가 통계 */
  aptTrade: async (params: {
    district_code: string;
    deal_ym?: string;
    months?: number;
    area_min?: number;
    area_max?: number;
  }): Promise<AptTradeStat> => {
    const res = await apiClient.get('/market/apt-trade', { params });
    return unwrap<AptTradeStat>(res.data);
  },

  /** 아파트 전세/월세 실거래가 통계 */
  aptRent: async (params: {
    district_code: string;
    deal_ym?: string;
    months?: number;
    area_min?: number;
    area_max?: number;
    rent_type?: RentType;
  }): Promise<AptRentStat> => {
    const res = await apiClient.get('/market/apt-rent', { params });
    return unwrap<AptRentStat>(res.data);
  },

  /**
   * 매매+전세(또는 월세) 통합 시세 (인증 필요, 무료 3회 쿼터).
   * 비2xx 응답(402 쿼터초과, 503 미설정 등)은 AxiosError로 throw되므로
   * 호출부에서 err.response?.status 로 분기 처리한다.
   */
  summary: async (params: {
    district_code: string;
    dong?: string;
    rent_type?: RentType;
    months?: number;
    deal_ym?: string;
    area_min?: number;
    area_max?: number;
  }): Promise<MarketSummaryResponse> => {
    const res = await apiClient.get('/market/summary', { params });
    return unwrap<MarketSummaryResponse>(res.data);
  },
};
