import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  ApiError,
  ackConsent,
  ackFirstTurnDisclosures,
  createAdvisorSession,
  createAvatarSession,
  listInvestors,
  mintDevToken,
  parseSseStream,
  sendAdvisorMessage,
  stopAvatarSession,
} from './advisor-service';
import { clearDevAuth, setDevAuth } from './dev-auth';
import type { AdvisorSseHandlers } from './advisor-types';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function problemResponse(code: string, message: string, status = 403): Response {
  return jsonResponse({ code, message }, status);
}

function encodeSse(events: Array<{ event: string; data: string }>): ReadableStream<Uint8Array> {
  const text = events.map((e) => `event: ${e.event}\ndata: ${e.data}\n\n`).join('');
  return new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(text));
      controller.close();
    },
  });
}

function sseResponse(events: Array<{ event: string; data: string }>): Response {
  return new Response(encodeSse(events), {
    status: 200,
    headers: { 'content-type': 'text/event-stream' },
  });
}

const sessionFixture = {
  thread_id: 'th_1',
  thread_started_at: '2026-08-02T04:00:00.000Z',
  capabilities: { chat: true, voice: true, advisory: true, transactional: false },
  disclosures_required: [],
  client: { first_name: 'Rodrigo', risk_category: 'moderado' },
};

const consentFixture = (overrides: Record<string, unknown> = {}) => ({
  type: 'privacy_notice',
  public_id: 'pub_1',
  current_version: 'v2',
  granted: false,
  granted_version: null,
  granted_at: null,
  revoked_at: null,
  required_for: 'first_turn',
  ...overrides,
});

function makeHandlers(): AdvisorSseHandlers {
  return {
    onToken: vi.fn(),
    onUi: vi.fn(),
    onCitations: vi.fn(),
    onFormSpec: vi.fn(),
    onError: vi.fn(),
    onDone: vi.fn(),
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  clearDevAuth();
});

describe('parseSseStream', () => {
  it('parses token and done events', async () => {
    const stream = encodeSse([
      { event: 'token', data: '{"text":"Hola"}' },
      {
        event: 'done',
        data: '{"turn_id":"tn_1","evidence_id":"ev_1","service_type":"asesorado"}',
      },
    ]);

    const events = [];
    for await (const item of parseSseStream(stream)) {
      events.push(item);
    }

    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ event: 'token', data: '{"text":"Hola"}' });
    expect(events[1]?.event).toBe('done');
  });
});

describe('createAdvisorSession', () => {
  it('posts channel and locale, returns the parsed session', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(sessionFixture));
    vi.stubGlobal('fetch', fetchMock);

    const session = await createAdvisorSession('chat');

    expect(session.thread_id).toBe('th_1');
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/sessions',
      expect.objectContaining({ method: 'POST' }),
    );
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(body.channel).toBe('chat');
    expect(typeof body.locale).toBe('string');
  });

  it('throws an ApiError carrying the problem+json code', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(problemResponse('CONSENT_REQUIRED', 'Consents missing')),
    );

    await expect(createAdvisorSession()).rejects.toMatchObject({
      name: 'ApiError',
      code: 'CONSENT_REQUIRED',
      message: 'Consents missing',
    });
  });
});

describe('ackConsent', () => {
  it('sends an Idempotency-Key header and the ack body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal('fetch', fetchMock);

    await ackConsent('privacy_notice', 'v2', 'chat');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/consents');
    expect(init.method).toBe('POST');
    expect(init.headers['idempotency-key']).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/,
    );
    expect(JSON.parse(init.body)).toEqual({
      type: 'privacy_notice',
      version: 'v2',
      granted: true,
      channel: 'chat',
    });
  });
});

describe('ackFirstTurnDisclosures', () => {
  it('acks only the ungranted first_turn consents', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          consents: [
            consentFixture({ type: 'privacy_notice', granted: true }),
            consentFixture({ type: 'ai_disclosure', current_version: 'v3' }),
            consentFixture({ type: 'voice_recording', required_for: 'voice' }),
          ],
        }),
      )
      .mockResolvedValue(jsonResponse({}));
    vi.stubGlobal('fetch', fetchMock);

    await ackFirstTurnDisclosures();

    expect(fetchMock).toHaveBeenCalledTimes(2);
    const [url, init] = fetchMock.mock.calls[1];
    expect(url).toBe('/api/v1/consents');
    expect(init.headers['idempotency-key']).toBeDefined();
    expect(JSON.parse(init.body)).toEqual({
      type: 'ai_disclosure',
      version: 'v3',
      granted: true,
      channel: 'chat',
    });
  });
});

describe('avatar endpoints', () => {
  it('creates a session with Idempotency-Key', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        avatar_session_id: 'as_1',
        livekit_url: 'wss://media.example/room',
        livekit_client_token: 'tk',
        max_session_duration_s: 300,
        expires_at: '2026-09-01T12:00:00Z',
        audio_ws_path: '/v1/avatar/as_1/audio',
        emulated: true,
      }),
    );
    vi.stubGlobal('fetch', fetchMock);

    const session = await createAvatarSession('th_1', 'portrait');

    expect(session.avatar_session_id).toBe('as_1');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/avatar/session');
    expect(init.headers['idempotency-key']).toBeDefined();
    expect(JSON.parse(init.body)).toEqual({ thread_id: 'th_1', orientation: 'portrait' });
  });

  it('stops a session with reason user', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal('fetch', fetchMock);

    await stopAvatarSession('as_1', 'user');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/avatar/session/stop');
    expect(init.headers['idempotency-key']).toBeDefined();
    expect(JSON.parse(init.body)).toEqual({ avatar_session_id: 'as_1', reason: 'user' });
  });
});

describe('investor switching', () => {
  const investorFixture = {
    id_cliente_pk: 1,
    numero_cliente_unico: 200001,
    nombre_completo: 'Mariano Gonzales Santiago',
    rfc: 'DAXI800214FE8',
    correo_electronico: 'mariano.gonzales@gmail.com',
    perfil_riesgo: 'Agresivo',
    total_contratos: 4,
  };

  it('lists investors from /v1/config/investors', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ investors: [investorFixture], total: 1 }));
    vi.stubGlobal('fetch', fetchMock);

    const list = await listInvestors();

    expect(list.total).toBe(1);
    expect(list.investors[0]).toMatchObject({
      numero_cliente_unico: 200001,
      perfil_riesgo: 'Agresivo',
    });
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/config/investors',
      expect.objectContaining({ headers: {} }),
    );
  });

  it('mints a dev token for the selected client_id', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({
          access_token: 'tok',
          client_id: '200001',
          token_type: 'Bearer',
          expires_in: 900,
        }),
      );
    vi.stubGlobal('fetch', fetchMock);

    const token = await mintDevToken('200001');

    expect(token.access_token).toBe('tok');
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/auth/dev-token');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ client_id: '200001' });
  });

  it('sends the stored dev token as a bearer header on session calls', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(sessionFixture));
    vi.stubGlobal('fetch', fetchMock);
    setDevAuth({ clientId: '200001', accessToken: 'tok', expiresAt: Date.now() + 60_000 });

    await createAdvisorSession('chat');

    const [, init] = fetchMock.mock.calls[0];
    expect(init.headers.authorization).toBe('Bearer tok');
  });
});

describe('sendAdvisorMessage', () => {
  it('posts {text} and dispatches every SSE event kind', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      sseResponse([
        { event: 'token', data: '{"text":"Hola"}' },
        {
          event: 'ui',
          data: '{"type":"market_quote","payload":{"symbol":"USDMXN","value":"18.42"}}',
        },
        { event: 'citations', data: '{"items":[{"title":"Banxico"}]}' },
        { event: 'form_spec', data: '{"form_id":"frm_1"}' },
        {
          event: 'done',
          data: '{"turn_id":"tn_1","evidence_id":"ev_1","service_type":"asesorado","disclosures_shown":{"privacy_notice":"v2"}}',
        },
      ]),
    );
    vi.stubGlobal('fetch', fetchMock);
    const handlers = makeHandlers();

    await sendAdvisorMessage('th_1', { text: '¿Cómo va mi portafolio?' }, handlers);

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/v1/threads/th_1/messages');
    expect(init.headers.accept).toBe('text/event-stream');
    expect(JSON.parse(init.body)).toEqual({ text: '¿Cómo va mi portafolio?' });

    expect(handlers.onToken).toHaveBeenCalledWith('Hola');
    expect(handlers.onUi).toHaveBeenCalledWith(expect.objectContaining({ type: 'market_quote' }));
    expect(handlers.onCitations).toHaveBeenCalledWith({ items: [{ title: 'Banxico' }] });
    expect(handlers.onFormSpec).toHaveBeenCalledWith(expect.objectContaining({ form_id: 'frm_1' }));
    expect(handlers.onDone).toHaveBeenCalledWith(
      expect.objectContaining({ turn_id: 'tn_1', service_type: 'asesorado' }),
    );
    expect(handlers.onError).not.toHaveBeenCalled();
  });

  it('surfaces problem+json errors as ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(problemResponse('CONSENT_REQUIRED', 'Ack disclosures first')),
    );
    const handlers = makeHandlers();

    await expect(sendAdvisorMessage('th_1', { text: 'Hola' }, handlers)).rejects.toBeInstanceOf(
      ApiError,
    );
  });
});
