import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],
    // In dev, proxy /api to the backend server
    ...(mode !== 'production' && {
      server: {
        port: 5173,
        proxy: {
          '/api': {
            target: env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
            changeOrigin: true,
          },
          '/public': {
            target: env.VITE_API_PROXY_TARGET || 'http://localhost:8000',
            changeOrigin: true,
          },
        },
      },
    }),
    build: {
      outDir: 'dist',
      sourcemap: false,
      // Chunk splitting for better caching
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom', 'react-router-dom'],
            forms: ['react-hook-form', '@hookform/resolvers', 'zod'],
          },
        },
      },
    },
    test: {
      globals: true,
      environment: 'happy-dom',
      setupFiles: ['./src/test/setup.ts'],
    },
  }
})
