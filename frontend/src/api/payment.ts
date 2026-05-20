import apiClient from './client';
import type {
  PaymentPrepareRequest,
  PaymentPrepareResponse,
  PaymentVerifyRequest,
  PaymentVerifyResponse,
  PaymentHistoryResponse,
} from '../types/api';

export const paymentApi = {
  prepare: async (req: PaymentPrepareRequest): Promise<PaymentPrepareResponse> => {
    const res = await apiClient.post<{ success: true; data: PaymentPrepareResponse }>(
      '/payment/prepare',
      req
    );
    return res.data.data;
  },

  verify: async (req: PaymentVerifyRequest): Promise<PaymentVerifyResponse> => {
    const res = await apiClient.post<{ success: true; data: PaymentVerifyResponse }>(
      '/payment/verify',
      req
    );
    return res.data.data;
  },

  history: async (): Promise<PaymentHistoryResponse> => {
    const res = await apiClient.get<{ success: true; data: PaymentHistoryResponse }>(
      '/payment/history'
    );
    return res.data.data;
  },
};
