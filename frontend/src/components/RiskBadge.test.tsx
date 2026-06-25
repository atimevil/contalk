import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import RiskBadge from './RiskBadge';

describe('RiskBadge', () => {
  it('renders high risk badge with "고위험" text', () => {
    render(<RiskBadge risk="high" />);
    expect(screen.getByText('고위험')).toBeInTheDocument();
  });

  it('renders medium risk badge with "위험" text', () => {
    render(<RiskBadge risk="medium" />);
    expect(screen.getByText('위험')).toBeInTheDocument();
  });

  it('renders caution badge with "주의" text', () => {
    render(<RiskBadge risk="caution" />);
    expect(screen.getByText('주의')).toBeInTheDocument();
  });

  it('renders safe badge with "정상" text', () => {
    render(<RiskBadge risk="safe" />);
    expect(screen.getByText('정상')).toBeInTheDocument();
  });

  it('hides label when showLabel is false', () => {
    render(<RiskBadge risk="safe" showLabel={false} />);
    expect(screen.queryByText('정상')).not.toBeInTheDocument();
  });

  it('has correct aria-label for accessibility', () => {
    render(<RiskBadge risk="caution" />);
    expect(screen.getByRole('status')).toHaveAttribute('aria-label', '위험도: 주의');
  });
});
