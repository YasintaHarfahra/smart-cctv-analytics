import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Ambil PORT dari environment, default ke 3001 kalau tidak ada
const PORT = process.env.PORT || 3001
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: PORT,
    proxy: {
      '/api': {
        target: BACKEND_URL,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
