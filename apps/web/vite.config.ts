import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import type { ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '../..');

function parseEnvFile(filePath: string): Record<string, string> {
  if (!fs.existsSync(filePath)) return {};
  const result: Record<string, string> = {};
  for (const line of fs.readFileSync(filePath, 'utf8').split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const idx = trimmed.indexOf('=');
    if (idx < 0) continue;
    const key = trimmed.slice(0, idx).trim();
    let value = trimmed.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    result[key] = value;
  }
  return result;
}

/** Read from .env files only — process.env empty strings must not override file values. */
function resolveAgentDevToken(mode: string): string {
  const candidates = [
    path.join(repoRoot, `.env.${mode}.local`),
    path.join(repoRoot, '.env.local'),
    path.join(repoRoot, `.env.${mode}`),
    path.join(repoRoot, '.env'),
    path.join(__dirname, '.env'),
  ];
  for (const file of candidates) {
    const value = parseEnvFile(file).AGENT_DEV_TOKEN;
    if (value) return value;
  }
  return process.env.AGENT_DEV_TOKEN ?? '';
}

export default defineConfig(({ mode }) => {
  const devToken = resolveAgentDevToken(mode);

  const advisorProxy: ProxyOptions = {
    target: 'http://localhost:8443',
    changeOrigin: true,
    secure: false,
    ws: true,
    rewrite: (requestPath) => requestPath.replace(/^\/api/, ''),
    configure: (proxy) => {
      proxy.on('proxyReq', (proxyReq) => {
        if (devToken) proxyReq.setHeader('Authorization', `Bearer ${devToken}`);
      });
      proxy.on('proxyReqWs', (proxyReq, req) => {
        if (!devToken) return;
        const url = new URL(req.url ?? '/', 'http://localhost');
        if (url.searchParams.has('access_token')) return;
        url.searchParams.set('access_token', devToken);
        proxyReq.path = `${url.pathname}${url.search}`;
      });
    },
  };

  const proxy = {
    '/api': advisorProxy,
  };

  return {
    envDir: repoRoot,
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
