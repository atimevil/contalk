import { useCallback, useRef } from 'react';
import { useDropzone, type FileRejection } from 'react-dropzone';

interface UploadError {
  code: 'FILE_TYPE_INVALID' | 'FILE_SIZE_EXCEEDED';
  message: string;
}

interface UploadZoneProps {
  accept?: string[];
  maxSizeMB?: number;
  onFileSelect: (file: File) => void;
  onError: (error: UploadError) => void;
  disabled?: boolean;
  className?: string;
}

export default function UploadZone({
  accept = ['image/jpeg', 'image/png', 'application/pdf'],
  maxSizeMB = 20,
  onFileSelect,
  onError,
  disabled = false,
  className = '',
}: UploadZoneProps) {
  const cameraInputRef = useRef<HTMLInputElement>(null);

  const validateAndSelect = useCallback(
    (file: File) => {
      if (!accept.includes(file.type)) {
        onError({ code: 'FILE_TYPE_INVALID', message: 'JPG, PNG, PDF 파일만 업로드 가능해요.' });
        return;
      }
      if (file.size > maxSizeMB * 1024 * 1024) {
        onError({ code: 'FILE_SIZE_EXCEEDED', message: `${maxSizeMB}MB 이하 파일만 가능해요.` });
        return;
      }
      onFileSelect(file);
    },
    [accept, maxSizeMB, onFileSelect, onError]
  );

  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: FileRejection[]) => {
      if (rejectedFiles.length > 0) {
        const errorCode = rejectedFiles[0].errors[0]?.code;
        if (errorCode === 'file-too-large') {
          onError({ code: 'FILE_SIZE_EXCEEDED', message: `${maxSizeMB}MB 이하 파일만 가능해요.` });
        } else {
          onError({ code: 'FILE_TYPE_INVALID', message: 'JPG, PNG, PDF 파일만 업로드 가능해요.' });
        }
        return;
      }
      if (acceptedFiles.length > 0) {
        onFileSelect(acceptedFiles[0]);
      }
    },
    [onFileSelect, onError, maxSizeMB]
  );

  const acceptMap = accept.reduce<Record<string, string[]>>((acc, type) => {
    acc[type] = [];
    return acc;
  }, {});

  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: acceptMap,
    maxSize: maxSizeMB * 1024 * 1024,
    disabled,
    multiple: false,
  });

  const borderStyle = isDragReject
    ? 'border-red-400 bg-red-50'
    : isDragActive
    ? 'border-brand-500 bg-brand-50 scale-[1.01] ring-2 ring-brand-300'
    : disabled
    ? 'border-slate-200 bg-slate-100 opacity-60 cursor-not-allowed'
    : 'border-slate-300 bg-slate-50 hover:border-brand-400 hover:bg-brand-50';

  const handleCameraClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // dropzone 클릭 이벤트 차단
    cameraInputRef.current?.click();
  };

  const handleCameraChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) validateAndSelect(file);
    // 같은 파일 재선택 가능하도록 초기화
    e.target.value = '';
  };

  return (
    <div
      {...getRootProps()}
      className={`min-h-[180px] rounded-xl border-2 border-dashed p-6 flex flex-col items-center justify-center text-center transition-all cursor-pointer ${borderStyle} ${className}`}
      aria-label="파일 업로드 영역"
    >
      {/* 드롭존 기본 input (파일 선택용) */}
      <input {...getInputProps()} aria-label="파일 선택" />

      {/* 카메라 전용 input — capture로 카메라 앱 바로 열기 */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={handleCameraChange}
        disabled={disabled}
        aria-label="카메라로 촬영"
      />

      <div className="text-3xl mb-3" aria-hidden="true">
        {isDragActive ? '📂' : '📄'}
      </div>

      {isDragActive ? (
        <p className="text-brand-600 font-medium">여기에 놓으세요!</p>
      ) : isDragReject ? (
        <p className="text-red-600 font-medium">지원하지 않는 파일 형식이에요.</p>
      ) : (
        <>
          <p className="text-slate-700 font-medium mb-1 text-sm">파일을 끌어다 놓거나</p>
          <p className="text-slate-500 text-xs mb-4">아래 버튼으로 선택하세요</p>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleCameraClick}
              disabled={disabled}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-sm text-slate-700 shadow-sm hover:bg-slate-50 disabled:opacity-50"
            >
              <span>📷</span> 사진 촬영
            </button>
            <span className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-200 rounded-lg text-sm text-slate-700 shadow-sm">
              <span>📁</span> 파일 선택
            </span>
          </div>
        </>
      )}

      <p className="text-xs text-slate-400 mt-3">JPG · PNG · PDF, 최대 {maxSizeMB}MB</p>
    </div>
  );
}
