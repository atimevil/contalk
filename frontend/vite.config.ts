import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // API 프록시 대상:
  //   Docker Compose 내부: backend 서비스명 사용
  //   로컬 직접 실행: VITE_API_URL 또는 localhost:8000 기본값
  const apiTarget = env.VITE_API_URL || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          // 연결 오류 시 로그 출력 (MSW 로 폴백됨)
          configure: (proxy) => {
            proxy.on('error', (err) => {
              console.warn('[vite proxy] 백엔드 연결 실패:', err.message)
            })
          },
        },
      },
    },
  }
})
