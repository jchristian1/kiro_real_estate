import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@/shared': path.resolve(__dirname, './src/shared'),
      '@/apps': path.resolve(__dirname, './src/apps'),
      '@/models': path.resolve(__dirname, './src/models'),
      '@/components': path.resolve(__dirname, './src/apps/agent/components'),
      '@/platform-admin-components': path.resolve(__dirname, './src/apps/platform-admin/components'),
      '@/agent-components': path.resolve(__dirname, './src/apps/agent/components'),
      '@/context': path.resolve(__dirname, './src/shared/contexts'),
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: './src/test/setup.ts',
  },
})
