import apiClient from './client';
import type {
  SpecialClausesResponse,
  UpdateSpecialClauseRequest,
  UpdateSpecialClauseResponse,
} from '../types/api';

export const specialClausesApi = {
  list: async (reportId: string): Promise<SpecialClausesResponse> => {
    const res = await apiClient.get<{ success: true; data: SpecialClausesResponse }>(
      `/analysis/${reportId}/special-clauses`
    );
    return res.data.data;
  },

  update: async (
    reportId: string,
    clauseId: string,
    req: UpdateSpecialClauseRequest
  ): Promise<UpdateSpecialClauseResponse> => {
    const res = await apiClient.patch<{ success: true; data: UpdateSpecialClauseResponse }>(
      `/analysis/${reportId}/special-clauses/${clauseId}`,
      req
    );
    return res.data.data;
  },

  downloadPdf: async (reportId: string): Promise<Blob> => {
    const res = await apiClient.get(`/analysis/${reportId}/special-clauses/pdf`, {
      responseType: 'blob',
    });
    return res.data;
  },
};
