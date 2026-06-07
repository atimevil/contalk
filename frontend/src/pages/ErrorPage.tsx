import { useSearchParams, useNavigate } from 'react-router-dom';
import PrimaryButton from '../components/PrimaryButton';

const ERROR_INFO: Record<string, { emoji: string; title: string; message: string; action: string; actionPath: string }> = {
  TIMEOUT: {
    emoji: '⏱',
    title: '분석 시간이 초과되었어요',
    message: '서버가 바쁜 것 같아요. 잠시 후 다시 시도해주세요.\n결제가 이루어진 경우 환불이 자동으로 처리됩니다.',
    action: '다시 분석하기',
    actionPath: '/upload',
  },
  SERVER_ERROR: {
    emoji: '😢',
    title: '서버 오류가 발생했어요',
    message: '일시적인 오류입니다. 잠시 후 다시 시도해주세요.\n문제가 지속되면 고객센터로 문의해주세요.',
    action: '처음으로',
    actionPath: '/',
  },
  NOT_FOUND: {
    emoji: '🔍',
    title: '페이지를 찾을 수 없어요',
    message: '요청하신 페이지가 존재하지 않아요.',
    action: '홈으로',
    actionPath: '/',
  },
};

export default function ErrorPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const code = params.get('code') || 'NOT_FOUND';
  const info = ERROR_INFO[code] || ERROR_INFO['NOT_FOUND'];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4">
      <div className="max-w-sm w-full text-center">
        <p className="text-6xl mb-4" aria-hidden="true">{info.emoji}</p>
        <h1 className="text-xl font-bold text-slate-900 mb-3">{info.title}</h1>
        <p className="text-sm text-slate-500 mb-8 leading-relaxed whitespace-pre-line">{info.message}</p>
        <PrimaryButton size="lg" fullWidth onClick={() => navigate(info.actionPath)}>
          {info.action}
        </PrimaryButton>
        <p className="text-xs text-slate-400 mt-4">오류 코드: {code}</p>
      </div>
    </div>
  );
}
