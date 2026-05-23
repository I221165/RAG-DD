import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Dev proxy: frontend calls /upload, /chat, etc. directly — Vite forwards
// to FastAPI on :8000. Avoids CORS friction during local dev.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/upload': 'http://localhost:8000',
      '/documents': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
      '/history': 'http://localhost:8000',
      '/session': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
    },
  },
})
