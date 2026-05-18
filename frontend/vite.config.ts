import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  base: '/',            // serve assets from root — backend mounts at /
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://localhost:8001', changeOrigin: true }
    }
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
  }
})
