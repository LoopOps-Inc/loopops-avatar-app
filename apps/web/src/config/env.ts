const env = import.meta.env;

function parseBool(value: string | undefined, fallback: boolean): boolean {
  if (value === undefined || value === '') return fallback;
  return value === 'true' || value === '1';
}

export const appEnv = {
  /** Base URL for the LiveAvatar REST API. Defaults to the dev proxy. */
  liveAvatarApiBase: env.VITE_LIVEAVATAR_API_BASE || '/liveavatar-api',
  /** Base URL for the advisor BFF. Defaults to the dev proxy. */
  advisorApiBase: env.VITE_ADVISOR_API_BASE || '/api',
  /**
   * When true, advisor calls use local fixtures instead of the BFF.
   * Defaults to true in dev so the UI works before apps/agent ships.
   */
  advisorMock: parseBool(env.VITE_ADVISOR_MOCK, env.DEV),
  /**
   * When true, "Start conversation" opens the live UI without minting a token
   * or starting a LiveAvatar stream (avoids sandbox session limits during UI work).
   */
  liveAvatarUiOnly: parseBool(env.VITE_LIVEAVATAR_UI_ONLY, env.DEV),
  isProd: env.PROD,
} as const;
