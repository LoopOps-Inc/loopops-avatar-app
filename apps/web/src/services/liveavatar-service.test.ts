import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createSandboxSessionToken } from './liveavatar-service';

const fetchMock = vi.fn();

describe('createSandboxSessionToken', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it('posts a FULL sandbox payload and returns the session token', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          code: 100,
          data: { session_id: 'sid-1', session_token: 'tok-1' },
          message: 'ok',
        }),
        { status: 200 },
      ),
    );

    await expect(createSandboxSessionToken()).resolves.toBe('tok-1');

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain('/v1/sessions/token');
    expect(init.method).toBe('POST');
    const body = JSON.parse(init.body as string);
    expect(body).toMatchObject({ mode: 'FULL', is_sandbox: true });
    expect(body.avatar_persona).toMatchObject({ language: 'es' });
    expect(body.avatar_persona).not.toHaveProperty('voice_id');
  });

  it('throws on HTTP error status', async () => {
    fetchMock.mockResolvedValueOnce(new Response('{}', { status: 401 }));

    await expect(createSandboxSessionToken()).rejects.toThrow('LiveAvatar (401)');
  });

  it('throws the API message when no token is returned', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ code: 400, data: null, message: 'sandbox avatar required' }), {
        status: 200,
      }),
    );

    await expect(createSandboxSessionToken()).rejects.toThrow('sandbox avatar required');
  });
});
