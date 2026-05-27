import type { RiskLevel } from '../types/api';

interface RiskBadgeProps {
  risk: RiskLevel;
  size?: 'sm' | 'md' | 'lg';
  showLabel?: boolean;
  className?: string;
}

const riskConfig: Record<RiskLevel, { emoji: string; label: string; className: string }> = {
  high: {
    emoji: '🚨',
    label: '위험',
    className: 'bg-red-50 text-red-600 border-red-200',
  },
  medium: {
    emoji: '🚨',
    label: '위험',
    className: 'bg-red-50 text-red-600 border-red-200',
  },
  caution: {
    emoji: '⚠️',
    label: '주의',
    className: 'bg-amber-50 text-amber-600 border-amber-200',
  },
  safe: {
    emoji: '✅',
    label: '정상',
    className: 'bg-green-50 text-green-700 border-green-200',
  },
};

const sizeConfig = {
  sm: 'h-5 text-xs px-2 rounded-sm',
  md: 'h-6 text-sm px-2.5 rounded',
  lg: 'h-7 text-sm font-medium px-3 rounded-md',
};

export default function RiskBadge({ risk, size = 'md', showLabel = true, className = '' }: RiskBadgeProps) {
  const config = riskConfig[risk];
  return (
    <span
      className={`inline-flex items-center gap-1 border font-medium ${sizeConfig[size]} ${config.className} ${className}`}
      role="status"
      aria-label={`위험도: ${config.label}`}
    >
      <span aria-hidden="true">{config.emoji}</span>
      {showLabel && <span>{config.label}</span>}
    </span>
  );
}
