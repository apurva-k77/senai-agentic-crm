import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': 'http://localhost:8000', '/ws': { target: 'ws://localhost:8000', ws: true }, '/dashboard': 'http://localhost:8000', '/threads': 'http://localhost:8000', '/analytics': 'http://localhost:8000', '/rag': 'http://localhost:8000', '/intelligence': 'http://localhost:8000', '/agent': 'http://localhost:8000', '/audit': 'http://localhost:8000', '/contacts': 'http://localhost:8000', '/emails': 'http://localhost:8000' } },
})
