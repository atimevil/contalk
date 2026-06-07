import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import NavBar from '../components/NavBar';
import BottomNavBar from '../components/BottomNavBar';
import UploadZone from '../components/UploadZone';
import PrimaryButton from '../components/PrimaryButton';
import { analysisApi } from '../api/analysis';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

export default function UploadPage() {
  const navigate = useNavigate();
  const { isLoggedIn } = useAuth();
  const { showToast } = useToast();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append('file', file);
      return analysisApi.upload(formData);
    },
    onSuccess: (data) => {
      navigate(`/analyzing/${data.jobId}`, { state: { estimatedSeconds: data.estimatedSeconds } });
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { error?: { code?: string; message?: string } } } };
      const code = err?.response?.data?.error?.code;
      const msg = err?.response?.data?.error?.message || '업로드에 실패했어요. 다시 시도해주세요.';

      if (code === 'QUOTA_EXCEEDED') {
        showToast({ type: 'warning', message: '이용권이 필요합니다.' });
        navigate('/payment');
        return;
      }

      showToast({ type: 'error', message: msg });
    },
  });

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setUploadError(null);
  };

  const handleFileError = (error: { code: string; message: string }) => {
    setUploadError(error.message);
    showToast({ type: 'error', message: error.message });
    setSelectedFile(null);
  };

  const handleAnalyze = () => {
    if (!selectedFile) return;

    if (!isLoggedIn) {
      navigate('/login', { state: { from: '/upload' } });
      return;
    }

    uploadMutation.mutate(selectedFile);
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setUploadError(null);
  };

  return (
    <div className="min-h-screen bg-slate-50 pb-20">
      <NavBar title="계약서 분석" showBack />

      <main className="max-w-3xl mx-auto px-4 pt-20 py-6 space-y-5">
        <div className="mb-2">
          <h2 className="text-lg font-bold text-slate-900 tracking-tight">계약서를 업로드하세요</h2>
          <p className="text-sm text-slate-500 mt-1">JPG · PNG · PDF 형식, 최대 20MB</p>
        </div>

        {/* 업로드 존 */}
        <UploadZone
          accept={['image/jpeg', 'image/png', 'application/pdf']}
          maxSizeMB={20}
          onFileSelect={handleFileSelect}
          onError={handleFileError}
          disabled={uploadMutation.isPending}
          className={uploadError ? 'border-red-400 bg-red-50' : ''}
        />

        {uploadError && (
          <p className="mt-2 text-sm text-red-600 flex items-center gap-1 font-medium" role="alert">
            <span>⚠️</span> {uploadError}
          </p>
        )}

        {/* 선택된 파일 미리보기 */}
        {selectedFile && (
          <div className="card">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center flex-shrink-0 border border-brand-100">
                  {selectedFile.type === 'application/pdf' ? (
                    <svg className="w-5 h-5 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5a1.5 1.5 0 001.5-1.5V5.25a1.5 1.5 0 00-1.5-1.5H3.75a1.5 1.5 0 00-1.5 1.5v14.25a1.5 1.5 0 001.5 1.5z" />
                    </svg>
                  )}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-bold text-slate-900 truncate">{selectedFile.name}</p>
                  <p className="text-xs text-slate-500">{formatFileSize(selectedFile.size)}</p>
                </div>
              </div>
              <button
                onClick={handleRemoveFile}
                disabled={uploadMutation.isPending}
                className="flex-shrink-0 text-slate-400 hover:text-red-500 text-lg leading-none focus:outline-none disabled:opacity-40 w-8 h-8 flex items-center justify-center rounded-lg hover:bg-red-50 transition-colors"
                aria-label="파일 삭제"
              >
                ×
              </button>
            </div>

            {/* 이미지 미리보기 */}
            {selectedFile.type !== 'application/pdf' && (
              <div className="mt-3 rounded-lg overflow-hidden border border-slate-200 h-32 bg-slate-50 flex items-center justify-center">
                <img
                  src={URL.createObjectURL(selectedFile)}
                  alt="계약서 미리보기"
                  className="max-h-full max-w-full object-contain"
                />
              </div>
            )}
          </div>
        )}

        {/* 분석 시작 버튼 */}
        <div className="mt-6">
          <PrimaryButton
            size="lg"
            fullWidth
            disabled={!selectedFile}
            loading={uploadMutation.isPending}
            onClick={handleAnalyze}
          >
            {uploadMutation.isPending ? '업로드 중...' : '분석 시작'}
          </PrimaryButton>
        </div>

        {!isLoggedIn && (
          <p className="text-center text-xs text-slate-400 mt-3">
            분석을 시작하려면 로그인이 필요합니다
          </p>
        )}

        {/* 안내 */}
        <div className="card bg-slate-50 border-slate-200 mt-6">
          <div className="flex gap-3">
            <svg className="w-5 h-5 text-slate-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
            <div className="text-xs text-slate-500 leading-relaxed space-y-1">
              <p>업로드된 계약서는 분석 후 30일간 암호화 보관되며, 이후 자동 삭제됩니다.</p>
              <p>분석 결과는 법률 조언이 아닌 정보 제공 목적이며, 중요 사항은 전문가에게 확인하세요.</p>
            </div>
          </div>
        </div>
      </main>

      <BottomNavBar />
    </div>
  );
}
