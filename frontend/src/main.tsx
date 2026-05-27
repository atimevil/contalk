import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css';

/**
 * MSW(Mock Service Worker) 활성화 여부 결정 로직:
 *
 *   VITE_ENABLE_MOCK=true   → 항상 Mock 활성화 (개발 중 API 없이 작업 시)
 *   VITE_ENABLE_MOCK=false  → 항상 Mock 비활성화 (실제 백엔드 연동)
 *   VITE_ENABLE_MOCK 미설정 → 개발 서버에서만 Mock 활성화 (기본값)
 *
 * .env 파일 또는 docker-compose.yml 의 environment 에서 설정한다.
 */
async function enableMocking(): Promise<void> {
  const mockEnvValue = import.meta.env.VITE_ENABLE_MOCK;

  // 명시적으로 false 로 설정된 경우 Mock 비활성화 (DEV 환경이어도 우선 적용)
  if (mockEnvValue === 'false') {
    console.info('[MSW] Mock 비활성화 — 실제 백엔드 API 사용');
    return;
  }

  // 명시적으로 true 인 경우에만 Mock 활성화 (DEV 자동 활성화 제거)
  if (mockEnvValue === 'true') {
    const { worker } = await import('./mocks/browser');
    await worker.start({
      onUnhandledRequest: 'bypass', // 미처리 요청은 그냥 통과 (실제 API로 전달)
    });
    console.info('[MSW] Mock 활성화');
  }
}

enableMocking().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
});
