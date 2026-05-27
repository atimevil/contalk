import apiClient from './client';
import type {
  UploadResponse,
  AnalysisStatusResponse,
  AnalysisResultResponse,
  QuotaResponse,
} from '../types/api';

export const analysisApi = {
  upload: async (formData: FormData): Promise<UploadResponse> => {
    const res = await apiClient.post<{ success: true; data: UploadResponse }>(
      '/analysis/upload',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 60000,
      }
    );
    return res.data.data;
  },

  getStatus: async (jobId: string): Promise<AnalysisStatusResponse> => {
    const res = await apiClient.get<{ success: true; data: AnalysisStatusResponse }>(
      `/analysis/${jobId}/status`
    );
    return res.data.data;
  },

  getResult: async (reportId: string): Promise<AnalysisResultResponse> => {
    const res = await apiClient.get<{ success: true; data: AnalysisResultResponse }>(
      `/analysis/${reportId}/result`
    );
    return res.data.data;
  },

  downloadPdf: async (reportId: string): Promise<Blob> => {
    const res = await apiClient.get(`/analysis/${reportId}/pdf`, {
      responseType: 'blob',
    });
    return res.data;
  },

  getQuota: async (): Promise<QuotaResponse> => {
    const res = await apiClient.get<{ success: true; data: QuotaResponse }>('/user/quota');
    return res.data.data;
  },

  getHistory: async (page = 1, perPage = 10): Promise<{ analyses: any[]; total: number }> => {
    const res = await apiClient.get<{
      success: true;
      data: { analyses: any[] };
      meta: { total: number };
    }>('/analysis/history', { params: { page, perPage } });
    return {
      analyses: res.data.data.analyses,
      total: res.data.meta?.total || 0,
    };
  },
};
