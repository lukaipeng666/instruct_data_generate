import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  // 加载环境变量，从项目根目录读取
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],
    server: {
      host: env.VITE_FRONTEND_HOST || '0.0.0.0',
      port: parseInt(env.VITE_FRONTEND_PORT) || 13000,
      proxy: {
        '/api': {
          target: env.VITE_BACKEND_PROXY_URL || 'http://localhost:18080',
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: '../static',
      emptyOutDir: true,
    },
  }
})

