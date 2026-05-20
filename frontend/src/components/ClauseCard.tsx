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
          <span className="text-xs text-gray-500 font-medium bg-white rounded px-2 py-0.5 border border-gray-200">
            {clause.clauseNumber}
          </span>
        )}
      </div>

      {/* 원문 */}
      <div className="bg-white bg-opacity-70 rounded-lg p-3 mb-3">
        <p className="text-sm text-gray-700 italic leading-relaxed line-clamp-3">
          "{clause.originalText}"
        </p>
      </div>

      {/* 쉬운 설명 */}
      <div>
        <p className="text-xs font-medium text-gray-500 mb-1">💬 쉬운 설명</p>
        <p className="text-sm text-gray-800 leading-relaxed">{clause.explanation}</p>
      </div>

      {/* 수정 권고 */}
      {clause.recommendation && (
        <div className="mt-3 bg-blue-50 rounded-lg p-3 border border-blue-200">
          <p className="text-xs font-medium text-blue-700 mb-1">📝 권고사항</p>
          <p className="text-sm text-blue-800">{clause.recommendation}</p>
        </div>
      )}

      {/* 법령 근거 아코디언 */}
      {clause.lawReference && (
        <div className="mt-3 border-t border-white border-opacity-50 pt-3">
          <button
            onClick={handleToggle}
            className="flex items-center gap-1 text-blue-600 text-sm font-medium hover:text-blue-700 focus:outline-none focus:underline"
            aria-expanded={expanded}
          >
            <span>{expanded ? '▲' : '▼'}</span>
            <span>법령 근거 {expanded ? '접기' : '보기'}</span>
          </button>

          {expanded && (
            <div className="mt-3 bg-white bg-opacity-70 rounded-lg p-3 text-sm text-gray-700 animate-fade-in">
              <p className="font-semibold text-gray-800 mb-1">
                {clause.lawReference.lawName} {clause.lawReference.article}
              </p>
              <p className="text-gray-600 mb-2">{clause.lawReference.summary}</p>
              {clause.lawReference.url && (
                <a
                  href={clause.lawReference.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:underline text-xs"
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
