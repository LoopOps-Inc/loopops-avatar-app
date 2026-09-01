const env = import.meta.env;

export const appEnv = {
  /** Base URL for the LiveAvatar REST API. Defaults to the dev proxy. */
  liveAvatarApiBase: env.VITE_LIVEAVATAR_API_BASE || '/liveavatar-api',
  isProd: env.PROD,
} as const;
