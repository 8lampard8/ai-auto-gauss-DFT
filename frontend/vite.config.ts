import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { nodePolyfills } from 'vite-plugin-node-polyfills'

// Dev: Vite on :5173 proxies /api to the FastAPI backend on :8000.
// Prod: the built bundle is served by FastAPI at /.
// nodePolyfills: Ketcher/Indigo transitively require Node builtins
// (util, assert, process) which must be polyfilled for the browser.
export default defineConfig({
  plugins: [
    react(),
    nodePolyfills({
      globals: { process: true, Buffer: true, global: true },
      include: ['util', 'assert', 'buffer', 'process', 'stream', 'events', 'path', 'crypto'],
    }),
  ],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
