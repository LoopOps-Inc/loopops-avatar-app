const env = import.meta.env;

export const appEnv = {
  /** Base URL for the agent backend. Defaults to the dev proxy. */
  advisorApiBase: env.VITE_ADVISOR_API_BASE || '/api',
  isProd: env.PROD,
} as const;
