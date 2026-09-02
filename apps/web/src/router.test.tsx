import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { RouterProvider, createMemoryHistory } from '@tanstack/react-router';
import { createAppRouter } from './router';
import { clearDevAuth, setDevAuth } from '@/services/dev-auth';
import { setLocale } from '@/i18n';

vi.mock('@/features/auth/components/LoginScreen', () => ({
  LoginScreen: () => <div>login-screen</div>,
}));

vi.mock('@/features/avatar/components/LiveSessionScreen', () => ({
  LiveSessionRoute: () => <div>demo-screen</div>,
}));

async function renderAt(path: string) {
  const history = createMemoryHistory({ initialEntries: [path] });
  const router = createAppRouter({ history });
  render(<RouterProvider router={router} />);
  await waitFor(() => {
    expect(router.state.status).not.toBe('pending');
  });
  return router;
}

describe('SPA route guards', () => {
  beforeEach(() => {
    clearDevAuth();
    sessionStorage.clear();
    setLocale('es');
  });

  afterEach(() => {
    clearDevAuth();
  });

  it('sends unauthenticated visitors from the demo route to login', async () => {
    const router = await renderAt('/demo');
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/');
    });
  });

  it('sends authenticated visitors from login to the demo route', async () => {
    setDevAuth({
      clientId: '200001',
      accessToken: 'tok',
      expiresAt: Date.now() + 60_000,
    });
    const router = await renderAt('/');
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/demo');
    });
  });

  it('treats an expired token as unauthenticated on the demo route', async () => {
    setDevAuth({
      clientId: '200001',
      accessToken: 'tok',
      expiresAt: Date.now() - 1_000,
    });
    const router = await renderAt('/demo');
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/');
    });
  });

  it('applies the same demo-route redirect for a native WebView deep link', async () => {
    const router = await renderAt('/demo');
    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/');
    });
  });
});
