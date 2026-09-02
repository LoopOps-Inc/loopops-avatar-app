export type DevAuth = {
  clientId: string;
  accessToken: string;
  expiresAt: number;
};

const STORAGE_KEY = 'actinver.dev-auth';

function readStored(): DevAuth | null {
  try {
    const raw = globalThis.sessionStorage?.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<DevAuth>;
    if (
      typeof parsed.accessToken !== 'string' ||
      typeof parsed.clientId !== 'string' ||
      typeof parsed.expiresAt !== 'number'
    ) {
      return null;
    }
    return parsed as DevAuth;
  } catch {
    return null;
  }
}

let current: DevAuth | null = readStored();

export function setDevAuth(auth: DevAuth | null): void {
  current = auth;
  try {
    if (auth) {
      globalThis.sessionStorage?.setItem(STORAGE_KEY, JSON.stringify(auth));
    } else {
      globalThis.sessionStorage?.removeItem(STORAGE_KEY);
    }
  } catch {
    return;
  }
}

export function clearDevAuth(): void {
  setDevAuth(null);
}

export function getDevAuth(): DevAuth | null {
  if (current && current.expiresAt <= Date.now()) {
    setDevAuth(null);
    return null;
  }
  return current;
}

export function authHeaders(): Record<string, string> {
  const auth = getDevAuth();
  return auth ? { authorization: `Bearer ${auth.accessToken}` } : {};
}
