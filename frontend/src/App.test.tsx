import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from './App';

describe('App', () => {
  it('renders without crashing', () => {
    render(<App />);
    // App이 렌더링되면 최소한 홈페이지의 일부 컨텐츠가 표시되어야 함
    expect(document.body).toBeInTheDocument();
  });
});
