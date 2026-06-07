import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PrimaryButton from './PrimaryButton';

describe('PrimaryButton', () => {
  it('renders children text', () => {
    render(<PrimaryButton>분석 시작</PrimaryButton>);
    expect(screen.getByText('분석 시작')).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const onClick = vi.fn();
    render(<PrimaryButton onClick={onClick}>클릭</PrimaryButton>);
    fireEvent.click(screen.getByText('클릭'));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it('does not call onClick when disabled', () => {
    const onClick = vi.fn();
    render(<PrimaryButton onClick={onClick} disabled>비활성</PrimaryButton>);
    fireEvent.click(screen.getByText('비활성'));
    expect(onClick).not.toHaveBeenCalled();
  });

  it('shows loading state', () => {
    render(<PrimaryButton loading>로딩중</PrimaryButton>);
    // loading 시 버튼이 disabled 상태여야 함
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
  });
});
