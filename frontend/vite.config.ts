import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: path.resolve(__dirname, '../src/iSponsorBlockTV/web/static'),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:42069',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:42069',
        ws: true,
      },
    },
  },
})
