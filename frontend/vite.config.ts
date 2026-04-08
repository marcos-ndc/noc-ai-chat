import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendUrl = env.VITE_BACKEND_URL || 'http://localhost:8000'
  const backendWs  = backendUrl.replace(/^http/, 'ws')

  return {
    plugins: [
      react(),
      VitePWA({
        registerType: 'autoUpdate',
        manifest: {
          name: 'NOC AI Chat',
          short_name: 'NOC AI',
          description: 'Agente de IA especializado em operações NOC',
          theme_color: '#0a0f1e',
          background_color: '#0a0f1e',
          display: 'standalone',
          icons: [
            { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
            { src: '/icon-512.png', sizes: '512x512', type: 'image/png' },
          ],
        },
      }),
    ],
    server: {
      port: 3000,
      host: '0.0.0.0',
      strictPort: true,
      proxy: {
        '/api': { target: backendUrl, changeOrigin: true },
        '/ws':  { target: backendWs,  ws: true, changeOrigin: true },
      },
    },
  }
})
