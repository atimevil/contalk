import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';

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
  const onDrop = useCallback(
    (acceptedFiles: File[], rejectedFiles: { file: File; errors: { code: string }[] }[]) => {
      if (rejectedFiles.length > 0) {
        const rejection = rejectedFiles[0];
        const errorCode = rejection.errors[0]?.code;
        if (errorCode === 'file-too-large') {
          onError({ code: 'FILE_SIZE_EXCEEDED', message: `20MB 이하 파일만 가능해요.` });
        } else {
          onError({ code: 'FILE_TYPE_INVALID', message: 'JPG, PNG, PDF 파일만 업로드 가능해요.' });
        }
        return;
      }
      if (acceptedFiles.length > 0) {
        onFileSelect(acceptedFiles[0]);
      }
    },
    [onFileSelect, onError]
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
    ? 'border-blue-500 bg-blue-50 scale-[1.01] ring-2 ring-blue-300'
    : disabled
    ? 'border-gray-200 bg-gray-100 opacity-60 cursor-not-allowed'
    : 'border-gray-300 bg-gray-50 hover:border-blue-400 hover:bg-blue-50';

  return (
    <div
      {...getRootProps()}
      className={`min-h-[200px] rounded-xl border-2 border-dashed p-8 flex flex-col items-center justify-center text-center transition-all cursor-pointer ${borderStyle} ${className}`}
      aria-label="파일 업로드 영역"
    >
      <input {...getInputProps()} aria-label="파일 선택" />

      <div className="text-4xl mb-3" aria-hidden="true">
        {isDragActive ? '📂' : '📄'}
      </div>

      {isDragActive ? (
        <p className="text-blue-600 font-medium">여기에 놓으세요!</p>
      ) : isDragReject ? (
        <p className="text-red-600 font-medium">지원하지 않는 파일 형식이에요.</p>
      ) : (
        <>
          <p className="text-gray-700 font-medium mb-1">파일을 여기에 끌어다 놓거나</p>
          <p className="text-gray-500 text-sm mb-4">탭해서 선택하세요</p>
          <div className="flex gap-3">
            <span className="inline-flex items-center gap-1.5 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 shadow-sm">
              <span>📷</span> 사진 촬영
            </span>
            <span className="inline-flex items-center gap-1.5 px-4 py-2 bg-white border border-gray-200 rounded-lg text-sm text-gray-700 shadow-sm">
              <span>📁</span> 파일 선택
            </span>
          </div>
        </>
      )}

      <p className="text-xs text-gray-400 mt-3">JPG · PNG · PDF, 최대 {maxSizeMB}MB</p>
    </div>
  );
}
