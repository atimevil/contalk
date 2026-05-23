import apiClient from './client';
import type {
  DistrictsResponse,
  AptTradeStat,
  AptRentStat,
  MarketSummaryResponse,
} from '../types/api';

export const marketApi = {
  /** 시도·시군구 코드 목록 (인증 불필요) */
  districts: async (): Promise<DistrictsResponse> => {
    const res = await apiClient.get<DistrictsResponse>('/market/districts');
    return res.data;
  },

  /** 아파트 매매 실거래가 통계 */
  aptTrade: async (params: {
    district_code: string;
    deal_ym?: string;
    area_min?: number;
    area_max?: number;
  }): Promise<AptTradeStat> => {
    const res = await apiClient.get<AptTradeStat>('/market/apt-trade', { params });
    return res.data;
  },

  /** 아파트 전세 실거래가 통계 */
  aptRent: async (params: {
    district_code: string;
    deal_ym?: string;
    area_min?: number;
    area_max?: number;
  }): Promise<AptRentStat> => {
    const res = await apiClient.get<AptRentStat>('/market/apt-rent', { params });
    return res.data;
  },

  /** 매매+전세 통합 시세 (전세가율 계산용) */
  summary: async (params: {
    district_code: string;
    deal_ym?: string;
    area_min?: number;
    area_max?: number;
  }): Promise<MarketSummaryResponse> => {
    const res = await apiClient.get<MarketSummaryResponse>('/market/summary', { params });
    return res.data;
  },
};
