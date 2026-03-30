import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@/shared': path.resolve(__dirname, './src/shared'),
        '@/models': path.resolve(__dirname, './src/models'),
        '@/apps': path.resolve(__dirname, './src/apps'),
        '@/components': path.resolve(__dirname, './src/apps/agent/components'),
        '@/platformAdminComponents': path.resolve(__dirname, './src/apps/platform-admin/components'),
        '@/agent-components': path.resolve(__dirname, './src/apps/agent/components'),
        '@/context': path.resolve(__dirname, './src/shared/contexts'),
        '@': path.resolve(__dirname, './src'),
      },
    },
    // In dev, proxy /api to the backend server
    ...(mode !== 'production' && {
      server: {
        port: 5173,
        proxy: {
          '/api': {
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
