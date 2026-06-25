// 시세/금액 표시용 포매터 — MarketPage·ChecklistPage 공용
// (기존 두 페이지에 동일하게 중복되어 있던 함수를 단일 출처로 통합)

/** 원 단위 금액을 "N억 N만원" 형태로 축약 */
export function formatKrw(amount: number): string {
  if (amount >= 100_000_000) {
    const eok = Math.floor(amount / 100_000_000);
    const man = Math.round((amount % 100_000_000) / 10_000);
    return man > 0 ? `${eok}억 ${man.toLocaleString()}만원` : `${eok}억원`;
  }
  if (amount >= 10_000) {
    return `${Math.round(amount / 10_000).toLocaleString()}만원`;
  }
  return `${amount.toLocaleString()}원`;
}

/** 입력 문자열에서 숫자만 추출해 천단위 콤마 포맷 */
export function formatNumber(value: string): string {
  const num = value.replace(/[^0-9]/g, '');
  return num ? parseInt(num).toLocaleString() : '';
}

/** 집계 기간 라벨 ("2026.03 ~ 2026.06 평균" 또는 "2026년 06월") */
export function formatPeriod(from?: string, to?: string, dealYm?: string): string {
  if (from && to) {
    return `${from.slice(0, 4)}.${from.slice(4)} ~ ${to.slice(0, 4)}.${to.slice(4)} 평균`;
  }
  if (dealYm) return `${dealYm.slice(0, 4)}년 ${dealYm.slice(4)}월`;
  return '';
}
