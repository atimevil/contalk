import { useState } from 'react';
import RiskBadge from './RiskBadge';
import type { AnalysisClause } from '../types/api';

interface ClauseCardProps {
  clause: AnalysisClause;
  isExpanded?: boolean;
  onExpand?: (id: string) => void;
}

export default function ClauseCard({ clause, isExpanded = false, onExpand }: ClauseCardProps) {
  const [expanded, setExpanded] = useState(isExpanded);

  const handleToggle = () => {
    setExpanded((prev) => !prev);
    onExpand?.(clause.id);
  };

  const borderColorMap = {
    high: 'border-red-200 bg-red-50',
    medium: 'border-orange-200 bg-orange-50',
    caution: 'border-amber-200 bg-amber-50',
    safe: 'border-green-200 bg-green-50',
  };

  return (
    <div className={`rounded-xl border shadow-card p-4 ${borderColorMap[clause.risk]}`}>
      {/* 상단 행 */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <RiskBadge risk={clause.risk} size="md" />
        {clause.clauseNumber && (
          <span className="text-xs text-slate-500 font-medium bg-white rounded px-2 py-0.5 border border-slate-200">
            {clause.clauseNumber}
          </span>
        )}
      </div>

      {/* 원문 */}
      <div className="bg-white bg-opacity-70 rounded-lg p-3 mb-3">
        <p className="text-sm text-slate-700 italic leading-relaxed line-clamp-3">
          "{clause.originalText}"
        </p>
      </div>

      {/* 쉬운 설명 — 정상 조항은 생략 */}
      {clause.risk !== 'safe' && (
        <div>
          <p className="text-xs font-medium text-slate-500 mb-1">💬 쉬운 설명</p>
          <p className="text-sm text-slate-800 leading-relaxed">
            {clause.explanation || '설명을 불러올 수 없습니다.'}
          </p>
        </div>
      )}

      {/* 권고사항 */}
      {clause.recommendation && (
        <div className="mt-3 bg-brand-50 rounded-lg p-3 border border-brand-200">
          <p className="text-xs font-medium text-brand-700 mb-1">📝 권고사항</p>
          <p className="text-sm text-brand-800">{clause.recommendation}</p>
        </div>
      )}

      {/* 법령 근거 아코디언 */}
      {clause.lawReference && (
        <div className="mt-3 border-t border-white border-opacity-50 pt-3">
          <button
            onClick={handleToggle}
            className="flex items-center gap-1 text-brand-600 text-sm font-medium hover:text-brand-700 focus:outline-none focus:underline"
            aria-expanded={expanded}
          >
            <span>{expanded ? '▲' : '▼'}</span>
            <span>법령 근거 {expanded ? '접기' : '보기'}</span>
          </button>

          {expanded && (
            <div className="mt-3 bg-white bg-opacity-70 rounded-lg p-3 text-sm text-slate-700 animate-fade-in">
              <p className="font-semibold text-slate-800 mb-1">
                {clause.lawReference.lawName} {clause.lawReference.article}
              </p>
              <p className="text-slate-600 mb-2">{clause.lawReference.summary}</p>
              {clause.lawReference.url && (
                <a
                  href={clause.lawReference.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand-600 hover:underline text-xs"
                >
                  🔗 국가법령정보센터에서 보기 →
                </a>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
