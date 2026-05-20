interface CircularCountdownProps {
  totalSeconds: number;
  remainingSeconds: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  dangerColor?: string;
}

export default function CircularCountdown({
  totalSeconds,
  remainingSeconds,
  size = 160,
  strokeWidth = 12,
  color = '#2563EB',
  dangerColor = '#EF4444',
}: CircularCountdownProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.max(0, remainingSeconds / totalSeconds);
  const strokeDashoffset = circumference * (1 - progress);
  const isDanger = remainingSeconds <= 10;
  const activeColor = isDanger ? dangerColor : color;

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
      role="timer"
      aria-label={`남은 시간 ${remainingSeconds}초`}
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
          stroke="#E5E7EB"
          strokeWidth={strokeWidth}
        />
        {/* 진행 원 */}
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
          style={{ transition: 'stroke-dashoffset 1s linear, stroke 0.3s ease' }}
        />
      </svg>

      {/* 중앙 텍스트 */}
      <div className="absolute flex flex-col items-center">
        <span
          className="text-4xl font-bold tabular-nums"
          style={{ color: activeColor, transition: 'color 0.3s ease' }}
        >
          {remainingSeconds}
        </span>
        <span className="text-xs text-gray-500 mt-0.5">남았어요</span>
      </div>
    </div>
  );
}
