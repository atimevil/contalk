import { useCallback } from 'react';
import { useNavigate, useParams, useLocation } from 'react-router-dom';
import AnalysisProgress from '../components/AnalysisProgress';
import { useToast } from '../context/ToastContext';

export default function AnalyzingPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const { showToast } = useToast();
  const estimatedSeconds = (location.state as { estimatedSeconds?: number })?.estimatedSeconds ?? 60;

  const handleComplete = useCallback(
    (reportId: string) => {
      navigate(`/report/${reportId}`, { replace: true });
    },
    [navigate]
  );

  const handleError = useCallback(
    (error: { code: string; message: string }) => {
      if (error.code === 'OCR_FAILED') {
        showToast({ type: 'error', message: '텍스트 인식에 실패했어요. 더 선명한 이미지를 올려주세요.' });
        navigate('/upload', { replace: true });
      } else if (error.code === 'ANALYSIS_TIMEOUT') {
        navigate('/error?code=TIMEOUT', { replace: true });
      } else {
        navigate('/error?code=SERVER_ERROR', { replace: true });
      }
    },
    [navigate, showToast]
  );

  if (!jobId) {
    navigate('/upload');
    return null;
  }

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">
      <header className="bg-white/95 backdrop-blur-sm border-b border-slate-200 h-14 flex items-center justify-center">
        <h1 className="text-sm font-bold text-slate-900 tracking-tight">계약서 분석 중</h1>
      </header>

      <main className="flex-1 max-w-3xl mx-auto w-full px-4 py-8">
        <AnalysisProgress
          jobId={jobId}
          totalSeconds={estimatedSeconds}
          onComplete={handleComplete}
          onError={handleError}
        />
      </main>
    </div>
  );
}
