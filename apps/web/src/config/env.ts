const env = import.meta.env;

export const appEnv = {
  /** Base URL for the agent backend. Defaults to the dev proxy. */
  advisorApiBase: env.VITE_ADVISOR_API_BASE || '/api',
  /** Shared dev password for POST /v1/auth/dev-token (must match agent AUTH_DEV_PASSWORD). */
  devPassword: env.VITE_DEV_PASSWORD || 'actinver123',
  isProd: env.PROD,
} as const;
