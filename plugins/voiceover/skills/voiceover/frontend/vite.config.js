import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Base './' so the SPA works when served behind a sub-path by FastAPI.
// Dev proxy forwards API + preview traffic to the backend dev server.
export default defineConfig({
  base: './',
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8091', changeOrigin: true },
      '/preview': { target: 'http://localhost:8091', changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})
