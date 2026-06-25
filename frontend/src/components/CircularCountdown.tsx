interface CircularCountdownProps {
  totalSeconds: number;
  remainingMs: number;      // 실제 남은 밀리초 (부모가 Date.now() 기반으로 계산)
  size?: number;
  strokeWidth?: number;
  color?: string;
  dangerColor?: string;
}

export default function CircularCountdown({
  totalSeconds,
  remainingMs,
  size = 160,
  strokeWidth = 12,
  color = '#0F2B5B',
  dangerColor = '#EF4444',
}: CircularCountdownProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  // 밀리초 단위 정밀 진행률 → 원호가 부드럽게 이동
  const progress = Math.max(0, Math.min(1, remainingMs / (totalSeconds * 1000)));
  const strokeDashoffset = circumference * (1 - progress);

  const displaySeconds = Math.ceil(remainingMs / 1000);
  const isDanger = remainingMs <= 10_000;
  const activeColor = isDanger ? dangerColor : color;

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="timer"
      aria-label={`남은 시간 ${displaySeconds}초`}
      aria-live="polite"
    >
      <svg
        width={size}
        height={size}
        className="-rotate-90"
        aria-hidden="true"
      >
        {/* 배경 원 */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#E2E8F0"
          strokeWidth={strokeWidth}
        />
        {/* 진행 원 — CSS 트랜지션 없음, 50ms 업데이트로 자연스럽게 */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={activeColor}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          style={{ transition: 'stroke 0.3s ease' }}
        />
      </svg>

      {/* 중앙 텍스트 */}
      <div className="absolute flex flex-col items-center">
        <span
          className="text-4xl font-bold tabular-nums"
          style={{ color: activeColor, transition: 'color 0.3s ease' }}
        >
          {displaySeconds}
        </span>
        <span className="text-xs text-slate-500 mt-0.5">남았어요</span>
      </div>
    </div>
  );
}
