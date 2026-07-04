import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev 時將 /api 轉去 Vercel dev（vercel dev 通常喺 3000）
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:3000'
    }
  }
})
