import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  // API 프록시 대상:
  //   Docker Compose 내부: process.env 로 직접 읽기 (loadEnv는 .env 파일만 읽음)
  //   로컬 직접 실행: .env 파일의 VITE_API_URL 또는 localhost:8000 기본값
  const apiTarget = process.env.VITE_API_URL || env.VITE_API_URL || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: 3000,
      watch: {
        usePolling: true,   // Windows + Docker 볼륨 마운트 환경에서 파일 변경 감지
      },
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          // 연결 오류 시 502 JSON 반환 (TCP 끊김 대신 → NS_ERROR_UNKNOWN_HOST 방지)
          configure: (proxy) => {
            proxy.on('error', (err, _req, res) => {
              console.warn('[vite proxy] 백엔드 연결 실패:', err.message)
              if ('writeHead' in res && !res.headersSent) {
                (res as import('http').ServerResponse).writeHead(502, { 'Content-Type': 'application/json' })
                res.end(JSON.stringify({
                  success: false,
                  error: { code: 'BACKEND_UNAVAILABLE', message: '백엔드 서버에 연결할 수 없습니다.' },
                }))
              }
            })
          },
        },
      },
    },
  }
})
