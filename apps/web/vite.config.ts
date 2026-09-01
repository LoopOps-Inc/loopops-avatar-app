import { defineConfig, loadEnv } from 'vite';
import type { ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  // Server-side only: the LiveAvatar API key is injected by the dev/preview
  // proxy and never bundled into client code. In production the service layer
  // should point at the backend that mints session tokens.
  const apiKey = env.LIVEAVATAR_API_KEY ?? '';

  const liveAvatarProxy: ProxyOptions = {
    target: 'https://api.liveavatar.com',
    changeOrigin: true,
    secure: true,
    rewrite: (requestPath) => requestPath.replace(/^\/liveavatar-api/, ''),
    headers: apiKey ? { 'X-API-KEY': apiKey } : {},
  };

  const proxy = { '/liveavatar-api': liveAvatarProxy };

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 8080,
      proxy,
    },
    preview: {
      port: 8080,
      proxy,
    },
    build: {
      outDir: 'dist',
    },
  };
});
