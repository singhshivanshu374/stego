import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/auth': 'http://127.0.0.1:8000',
      '/encode': 'http://127.0.0.1:8000',
      '/decode': 'http://127.0.0.1:8000',
      '/operations': 'http://127.0.0.1:8000',
      '/storage': 'http://127.0.0.1:8000',
    }
  }
})
