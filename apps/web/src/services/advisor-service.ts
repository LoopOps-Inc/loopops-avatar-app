import {
  type AvatarSessionResponse,
  type ChatMessageRequest,
  type ClientConfigResponse,
  type ConsentType,
  type ConsentsResponse,
  type DevTokenResponse,
  type InvestorsListResponse,
  type SessionResponse,
  AvatarSessionResponseSchema,
  ClientConfigResponseSchema,
  ConsentsResponseSchema,
  DevTokenResponseSchema,
  InvestorsListResponseSchema,
  SessionResponseSchema,
  SseCitationsEventSchema,
  SseDoneEventSchema,
  SseErrorEventSchema,
  SseFormSpecEventSchema,
  SseTokenEventSchema,
  UIComponentSchema,
} from '@loopops/contracts';
import { z } from 'zod';
import { appEnv } from '@/config/env';
import { getLocale } from '@/i18n';
import { authHeaders } from './dev-auth';
import type { AdvisorSseHandlers } from './advisor-types';

export type { AdvisorSseHandlers } from './advisor-types';

export class ApiError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
  }
}

async function throwProblem(res: Response): Promise<never> {
  let code = `HTTP_${res.status}`;
  let message = `Request failed (${res.status})`;
  try {
    const body = (await res.json()) as { code?: unknown; message?: unknown };
    if (typeof body?.code === 'string' && body.code) code = body.code;
    if (typeof body?.message === 'string' && body.message) message = body.message;
  } catch {
    // Not application/problem+json: keep the HTTP fallback.
  }
  throw new ApiError(code, message);
}

function idempotencyKey(): string {
  return crypto.randomUUID();
}

export async function* parseSseStream(
  body: ReadableStream<Uint8Array>,
): AsyncGenerator<{ event: string; data: string }> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const parts = buffer.split(/\r?\n\r?\n/);
    buffer = parts.pop() ?? '';

    for (const part of parts) {
      if (!part.trim()) continue;
      let event = 'message';
      const dataLines: string[] = [];
      for (const line of part.split('\n')) {
        if (line.startsWith('event:')) {
          event = line.slice(6).trim();
        } else if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trim());
        }
      }
      if (dataLines.length > 0) {
        yield { event, data: dataLines.join('\n') };
      }
    }
  }
}

async function dispatchSseEvent(
  event: string,
  data: string,
  handlers: AdvisorSseHandlers,
): Promise<void> {
  const parsed: unknown = JSON.parse(data);
  switch (event) {
    case 'token': {
      const token = SseTokenEventSchema.parse(parsed);
      handlers.onToken(token.text);
      break;
    }
    case 'ui': {
      const ui = UIComponentSchema.parse(parsed);
      handlers.onUi(ui);
      break;
    }
    case 'citations': {
      const citations = SseCitationsEventSchema.parse(parsed);
      handlers.onCitations(citations);
      break;
    }
    case 'form_spec': {
      const form = SseFormSpecEventSchema.parse(parsed);
      handlers.onFormSpec(form);
      break;
    }
    case 'error': {
      const error = SseErrorEventSchema.parse(parsed);
      handlers.onError(error);
      break;
    }
    case 'done': {
      const done = SseDoneEventSchema.parse(parsed);
      handlers.onDone(done);
      break;
    }
    default:
      break;
  }
}

export async function createAdvisorSession(
  channel: 'chat' | 'voice' = 'chat',
): Promise<SessionResponse> {
  const res = await fetch(`${appEnv.advisorApiBase}/v1/sessions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ channel, locale: getLocale() }),
  });
  if (!res.ok) {
    await throwProblem(res);
  }
  const json: unknown = await res.json();
  return SessionResponseSchema.parse(json);
}

export async function getConsents(): Promise<ConsentsResponse> {
  const res = await fetch(`${appEnv.advisorApiBase}/v1/consents`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) {
    await throwProblem(res);
  }
  const json: unknown = await res.json();
  return ConsentsResponseSchema.parse(json);
}

export async function ackConsent(
  type: ConsentType,
  version: string,
  channel: 'chat' | 'voice' | 'app' = 'app',
): Promise<void> {
  const res = await fetch(`${appEnv.advisorApiBase}/v1/consents`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'idempotency-key': idempotencyKey(),
      ...authHeaders(),
    },
    body: JSON.stringify({ type, version, granted: true, channel }),
  });
  if (!res.ok) {
    await throwProblem(res);
  }
}

export async function ackFirstTurnDisclosures(): Promise<void> {
  const { consents } = await getConsents();
  const pending = consents.filter(
    (consent) => consent.required_for === 'first_turn' && !consent.granted,
  );
  for (const consent of pending) {
    await ackConsent(consent.type, consent.current_version, 'chat');
  }
}

export async function ackVoiceConsent(): Promise<void> {
  const { consents } = await getConsents();
  const voice = consents.find((consent) => consent.type === 'voice_recording');
  if (voice && !voice.granted) {
    await ackConsent(voice.type, voice.current_version, 'voice');
  }
}

export async function getClientConfig(): Promise<ClientConfigResponse> {
  const res = await fetch(`${appEnv.advisorApiBase}/v1/config`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) {
    await throwProblem(res);
  }
  const json: unknown = await res.json();
  return ClientConfigResponseSchema.parse(json);
}

export async function listInvestors(): Promise<InvestorsListResponse> {
  const res = await fetch(`${appEnv.advisorApiBase}/v1/config/investors`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) {
    await throwProblem(res);
  }
  const json: unknown = await res.json();
  return InvestorsListResponseSchema.parse(json);
}

export async function mintDevToken(clientId: string, password: string): Promise<DevTokenResponse> {
  const res = await fetch(`${appEnv.advisorApiBase}/v1/auth/dev-token`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ client_id: clientId, password }),
  });
  if (!res.ok) {
    await throwProblem(res);
  }
  const json: unknown = await res.json();
  return DevTokenResponseSchema.parse(json);
}

const AvatarPreflightResponseSchema = z.object({
  media_reachable: z.boolean(),
  voice_offered: z.boolean(),
  reason: z.string().optional(),
});

export async function avatarPreflight(): Promise<z.infer<typeof AvatarPreflightResponseSchema>> {
  const res = await fetch(`${appEnv.advisorApiBase}/v1/avatar/preflight`, {
    headers: { ...authHeaders() },
  });
  if (!res.ok) {
    await throwProblem(res);
  }
  const json: unknown = await res.json();
  return AvatarPreflightResponseSchema.parse(json);
}

export async function createAvatarSession(
  threadId: string,
  orientation: 'portrait' | 'landscape' = 'portrait',
): Promise<AvatarSessionResponse> {
  const res = await fetch(`${appEnv.advisorApiBase}/v1/avatar/session`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'idempotency-key': idempotencyKey(),
      ...authHeaders(),
    },
    body: JSON.stringify({ thread_id: threadId, orientation }),
  });
  if (!res.ok) {
    await throwProblem(res);
  }
  const json: unknown = await res.json();
  return AvatarSessionResponseSchema.parse(json);
}

export async function stopAvatarSession(
  avatarSessionId: string,
  reason: 'user' | 'background' = 'user',
): Promise<void> {
  const res = await fetch(`${appEnv.advisorApiBase}/v1/avatar/session/stop`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'idempotency-key': idempotencyKey(),
      ...authHeaders(),
    },
    body: JSON.stringify({ avatar_session_id: avatarSessionId, reason }),
  });
  if (!res.ok) {
    await throwProblem(res);
  }
}

export async function sendAdvisorMessage(
  threadId: string,
  request: ChatMessageRequest,
  handlers: AdvisorSseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${appEnv.advisorApiBase}/v1/threads/${threadId}/messages`, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      accept: 'text/event-stream',
      ...authHeaders(),
    },
    body: JSON.stringify(request),
    signal,
  });

  if (!res.ok) {
    await throwProblem(res);
  }
  if (!res.body) {
    throw new ApiError('EMPTY_STREAM', 'The chat stream closed without events');
  }

  for await (const { event, data } of parseSseStream(res.body)) {
    await dispatchSseEvent(event, data, handlers);
  }
}
