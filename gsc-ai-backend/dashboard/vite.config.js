import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy API calls to the orchestrator so we avoid CORS issues in dev.
// All /api/* requests are forwarded to http://localhost:8000 with the
// /api prefix stripped, and WebSocket connections are proxied too.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
    },
  },
})
