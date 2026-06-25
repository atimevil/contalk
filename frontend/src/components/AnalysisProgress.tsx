import { useState, useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { analysisApi } from '../api/analysis';
import CircularCountdown from './CircularCountdown';
import type { AnalysisStepId } from '../types/api';

interface AnalysisStep {
  id: AnalysisStepId;
  label: string;
}

const DEFAULT_STEPS: AnalysisStep[] = [
  { id: 'upload', label: '파일 업로드 완료' },
  { id: 'ocr', label: '텍스트 인식(OCR) 완료' },
  { id: 'analyze', label: '위험 조항 분석 중...' },
  { id: 'clause', label: '특약 추천 준비 중' },
];

const TIPS = [
  '확정일자를 받지 않으면 집이 경매로 넘어가도 보증금을 못 돌려받을 수 있어요.',
  '전입신고는 이사 후 14일 이내에 반드시 해야 대항력이 생겨요.',
  '전세가율이 70%를 넘으면 위험 신호예요. 꼭 확인하세요.',
  '등기부등본은 계약 직전에 다시 한 번 확인하세요. 근저당이 설정될 수 있어요.',
  '계약서에 특약사항을 반드시 직접 확인하세요. 구두 약속은 효력이 없어요.',
];

interface AnalysisProgressProps {
  jobId: string;
  totalSeconds?: number;
  onComplete: (reportId: string) => void;
  onError: (error: { code: string; message: string }) => void;
  pollingInterval?: number;
}

export default function AnalysisProgress({
  jobId,
  totalSeconds = 60,
  onComplete,
  onError,
  pollingInterval = 2000,
}: AnalysisProgressProps) {
  const [remainingMs, setRemainingMs] = useState(totalSeconds * 1000);
  const [currentTipIndex, setCurrentTipIndex] = useState(0);
  const startTimeRef = useRef(Date.now());
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const tipIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasCompletedRef = useRef(false);

  const { data: statusData } = useQuery({
    queryKey: ['analysis-status', jobId],
    queryFn: () => analysisApi.getStatus(jobId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === 'completed' || data?.status === 'failed') return false;
      return pollingInterval;
    },
    enabled: !!jobId,
  });

  // 카운트다운 — Date.now() 기준 50ms 갱신으로 원호를 부드럽게
  useEffect(() => {
    startTimeRef.current = Date.now();
    intervalRef.current = setInterval(() => {
      const elapsed = Date.now() - startTimeRef.current;
      const remaining = Math.max(0, totalSeconds * 1000 - elapsed);
      setRemainingMs(remaining);
    }, 50);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [totalSeconds]);

  // 팁 슬라이드
  useEffect(() => {
    tipIntervalRef.current = setInterval(() => {
      setCurrentTipIndex((prev) => (prev + 1) % TIPS.length);
    }, 5000);

    return () => {
      if (tipIntervalRef.current) clearInterval(tipIntervalRef.current);
    };
  }, []);

  // 완료/실패 처리
  useEffect(() => {
    if (!statusData || hasCompletedRef.current) return;

    if (statusData.status === 'completed' && statusData.reportId) {
      hasCompletedRef.current = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
      setTimeout(() => onComplete(statusData.reportId!), 300);
    } else if (statusData.status === 'failed') {
      hasCompletedRef.current = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
      onError({
        code: statusData.errorCode || 'ANALYSIS_FAILED',
        message: statusData.errorMessage || '분석에 실패했어요.',
      });
    }
  }, [statusData, onComplete, onError]);

  // 타임아웃
  useEffect(() => {
    if (remainingMs === 0 && !hasCompletedRef.current) {
      hasCompletedRef.current = true;
      if (intervalRef.current) clearInterval(intervalRef.current);
      onError({ code: 'ANALYSIS_TIMEOUT', message: '분석 시간이 초과되었어요.' });
    }
  }, [remainingMs, onError]);

  const completedSteps = statusData?.completedSteps || [];
  const currentStep = statusData?.currentStep;
  const progress = statusData?.progress || 0;

  function getStepStatus(stepId: AnalysisStepId): 'done' | 'running' | 'pending' {
    if (completedSteps.includes(stepId)) return 'done';
    if (currentStep === stepId) return 'running';
    return 'pending';
  }

  const stepIcons = { done: '✅', running: '🔄', pending: '⏳' };

  return (
    <div className="flex flex-col items-center gap-6 py-6">
      {/* 원형 카운트다운 */}
      <CircularCountdown
        totalSeconds={totalSeconds}
        remainingMs={remainingMs}
        size={160}
      />

      {/* 선형 진행바 */}
      <div className="w-full">
        <div className="w-full bg-slate-200 rounded-full h-2 overflow-hidden">
          <div
            className="bg-brand-600 h-2 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
            role="progressbar"
            aria-valuenow={progress}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`분석 진행률 ${progress}%`}
          />
        </div>
        <p className="text-right text-xs text-slate-500 mt-1">{progress}%</p>
      </div>

      {/* 단계 체크리스트 */}
      <div className="w-full space-y-3">
        <p className="text-sm font-medium text-slate-700">현재 분석 단계:</p>
        {DEFAULT_STEPS.map((step) => {
          const status = getStepStatus(step.id);
          return (
            <div
              key={step.id}
              className={`flex items-center gap-3 text-sm ${
                status === 'done'
                  ? 'text-slate-700'
                  : status === 'running'
                  ? 'text-brand-600 font-medium'
                  : 'text-slate-400'
              }`}
              aria-live={status === 'running' ? 'polite' : undefined}
            >
              <span className={status === 'running' ? 'animate-spin-slow' : ''} aria-hidden="true">
                {stepIcons[status]}
              </span>
              <span>{step.label}</span>
            </div>
          );
        })}
      </div>

      {/* 팁 카드 */}
      <div className="w-full bg-brand-50 border border-brand-200 rounded-xl p-4 animate-fade-in">
        <p className="text-xs font-semibold text-brand-700 mb-2">💡 잠깐, 알고 계셨나요?</p>
        <p className="text-sm text-brand-900 leading-relaxed">{TIPS[currentTipIndex]}</p>
      </div>

      <p className="text-xs text-slate-400 text-center">
        분석 결과는 이메일로도 보내드려요.
      </p>
    </div>
  );
}
