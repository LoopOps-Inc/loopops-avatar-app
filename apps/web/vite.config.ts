import { createHmac, randomUUID } from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import type { ProxyOptions } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, '../..');

const DEV_ISSUER = 'https://idp.local.actinver/';
const DEV_AUDIENCE = 'actinver-ai-advisor';
const DEV_CLIENT_ID = 'cl_demo_moderado';

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

function loadRepoEnv(mode: string): Record<string, string> {
  const merged: Record<string, string> = {};
  for (const file of [
    path.join(repoRoot, `.env.${mode}.local`),
    path.join(repoRoot, '.env.local'),
    path.join(repoRoot, `.env.${mode}`),
    path.join(repoRoot, '.env'),
    path.join(__dirname, '.env'),
  ]) {
    Object.assign(merged, parseEnvFile(file));
  }
  return merged;
}

function b64url(value: string | Buffer): string {
  return Buffer.from(value).toString('base64url');
}

/** Mint an HS256 dev token matching services/agent/scripts/dev_token.py. */
function mintDevToken(signingKey: string, ttlS: number): string {
  const header = b64url(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const now = Math.floor(Date.now() / 1000);
  const payload = b64url(
    JSON.stringify({
      iss: DEV_ISSUER,
      aud: DEV_AUDIENCE,
      sub: DEV_CLIENT_ID,
      iat: now,
      exp: now + ttlS,
      jti: randomUUID().replace(/-/g, ''),
      roles: [],
    }),
  );
  const signingInput = `${header}.${payload}`;
  const signature = createHmac('sha256', signingKey).update(signingInput).digest('base64url');
  return `${signingInput}.${signature}`;
}

/**
 * Resolve the bearer token on each proxied request so edits to repo-root `.env`
 * take effect without restarting Vite. Prefer minting from DEV_SIGNING_KEY
 * (must match AUTH_DEV_SIGNING_KEY on the agent).
 */
function resolveAgentDevToken(mode: string): string {
  const env = loadRepoEnv(mode);
  const ttl = Number.parseInt(env.AUTH_ACCESS_TOKEN_MAX_TTL_S ?? '604800', 10);
  const signingKey = env.DEV_SIGNING_KEY || env.AUTH_DEV_SIGNING_KEY;
  if (signingKey) {
    return mintDevToken(signingKey, Number.isFinite(ttl) ? ttl : 604800);
  }
  return env.AGENT_DEV_TOKEN ?? '';
}

export default defineConfig(({ mode }) => {
  const advisorProxy: ProxyOptions = {
    target: 'http://localhost:8443',
    changeOrigin: true,
    secure: false,
    ws: true,
    rewrite: (requestPath) => requestPath.replace(/^\/api/, ''),
    configure: (proxy) => {
      proxy.on('proxyReq', (proxyReq) => {
        const devToken = resolveAgentDevToken(mode);
        if (devToken) {
          proxyReq.setHeader('Authorization', `Bearer ${devToken}`);
        }
      });
      proxy.on('proxyReqWs', (proxyReq, req) => {
        const devToken = resolveAgentDevToken(mode);
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

  const devToken = resolveAgentDevToken(mode);
  if (mode === 'development') {
    if (devToken) {
      console.info('[vite] Agent dev auth: proxy will inject a bearer token on /api');
    } else {
      console.warn(
        '[vite] Agent dev auth: set DEV_SIGNING_KEY in repo-root .env (or AGENT_DEV_TOKEN)',
      );
    }
  }

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
