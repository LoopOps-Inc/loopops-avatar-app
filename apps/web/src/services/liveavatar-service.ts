import { appEnv } from '@/config/env';
import { liveAvatarSandbox } from '@/config/avatar';

type SessionTokenResponse = {
  code: number;
  data: { session_id: string; session_token: string } | null;
  message: string;
};

/**
 * Mint a FULL-mode sandbox session token.
 * The API key is injected by the Vite dev proxy; in production this call
 * should go through the backend that holds the key.
 * https://docs.liveavatar.com/docs/sandbox-mode
 */
export async function createSandboxSessionToken(): Promise<string> {
  const res = await fetch(`${appEnv.liveAvatarApiBase}/v1/sessions/token`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      mode: 'FULL',
      is_sandbox: true,
      avatar_id: liveAvatarSandbox.avatarId,
      avatar_persona: {
        language: liveAvatarSandbox.language,
      },
    }),
  });

  if (!res.ok) {
    throw new Error(`LiveAvatar token request failed (${res.status})`);
  }

  const json = (await res.json()) as SessionTokenResponse;
  const token = json.data?.session_token;
  if (!token) {
    throw new Error(json.message || 'LiveAvatar did not return a session token');
  }
  return token;
}
