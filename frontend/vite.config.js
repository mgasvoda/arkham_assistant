import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/cards': 'http://localhost:8000',
      '/characters': 'http://localhost:8000',
      '/decks': 'http://localhost:8000',
      '/sim': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './tests/setup.js',
  },
})

