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
      formData.append('contractType', 'unknown');
      return analysisApi.upload(formData);
    },
    onSuccess: (data) => {
      navigate(`/analyzing/${data.jobId}`, { state: { estimatedSeconds: data.estimatedSeconds } });
    },
    onError: (error: unknown) => {
      const err = error as { response?: { data?: { error?: { message?: string } } } };
      const msg = err?.response?.data?.error?.message || '업로드에 실패했어요. 다시 시도해주세요.';
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
    <div className="min-h-screen bg-gray-50 pb-20">
      <NavBar title="계약서 업로드" showBack />

      <main className="max-w-2xl mx-auto px-4 pt-20 py-6">
        <div className="mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-1">어떤 파일을 올려주실 건가요?</h2>
          <p className="text-sm text-gray-400">JPG · PNG · PDF, 최대 20MB</p>
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
          <p className="mt-2 text-sm text-red-600 flex items-center gap-1" role="alert">
            <span>⚠️</span> {uploadError}
          </p>
        )}

        {/* 선택된 파일 미리보기 */}
        {selectedFile && (
          <div className="mt-4 bg-white border border-gray-200 rounded-xl p-4 shadow-card">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-3 min-w-0">
                <span className="text-2xl flex-shrink-0" aria-hidden="true">
                  {selectedFile.type === 'application/pdf' ? '📄' : '🖼️'}
                </span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">{selectedFile.name}</p>
                  <p className="text-xs text-gray-500">{formatFileSize(selectedFile.size)}</p>
                </div>
              </div>
              <button
                onClick={handleRemoveFile}
                disabled={uploadMutation.isPending}
                className="flex-shrink-0 text-gray-400 hover:text-red-500 text-lg leading-none focus:outline-none disabled:opacity-40"
                aria-label="파일 삭제"
              >
                ×
              </button>
            </div>

            {/* 이미지 미리보기 */}
            {selectedFile.type !== 'application/pdf' && (
              <div className="mt-3 rounded-lg overflow-hidden border border-gray-100 h-48 bg-gray-50 flex items-center justify-center">
                <img
                  src={URL.createObjectURL(selectedFile)}
                  alt="계약서 미리보기"
                  className="max-h-full max-w-full object-contain"
                />
              </div>
            )}

            {/* PDF 미리보기 (텍스트) */}
            {selectedFile.type === 'application/pdf' && (
              <div className="mt-3 rounded-lg border border-gray-100 h-48 bg-gray-50 flex items-center justify-center">
                <div className="text-center text-gray-400">
                  <p className="text-4xl mb-2" aria-hidden="true">📄</p>
                  <p className="text-sm">PDF 파일</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* 개인정보 안내 */}
        <div className="mt-4 flex items-start gap-2 text-xs text-gray-400">
          <span aria-hidden="true">⚠️</span>
          <p>개인정보가 포함된 경우 분석 후 즉시 파일이 삭제됩니다.</p>
        </div>

        {/* 분석 시작 버튼 */}
        <div className="mt-6">
          <PrimaryButton
            size="lg"
            fullWidth
            disabled={!selectedFile}
            loading={uploadMutation.isPending}
            onClick={handleAnalyze}
          >
            {uploadMutation.isPending ? '업로드 중...' : '분석 시작하기 →'}
          </PrimaryButton>
        </div>

        {!isLoggedIn && (
          <p className="text-center text-xs text-gray-400 mt-3">
            분석을 시작하려면 로그인이 필요해요
          </p>
        )}
      </main>

      <BottomNavBar />
    </div>
  );
}
