import {
  type ChatMessageRequest,
  type SessionResponse,
  SessionResponseSchema,
  SseDoneEventSchema,
  SseErrorEventSchema,
  SseTokenEventSchema,
  UIComponentSchema,
} from '@loopops/contracts';
import { appEnv } from '@/config/env';
import { createMockAdvisorSession, sendMockAdvisorMessage } from './advisor-mock';
import type { AdvisorSseHandlers } from './advisor-types';

export type { AdvisorSseHandlers } from './advisor-types';

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

    const parts = buffer.split('\n\n');
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

export async function createAdvisorSession(): Promise<SessionResponse> {
  if (appEnv.advisorMock) {
    return createMockAdvisorSession();
  }

  const res = await fetch(`${appEnv.advisorApiBase}/v1/sessions`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
  });
  if (!res.ok) {
    throw new Error(`Session request failed (${res.status})`);
  }
  const json: unknown = await res.json();
  return SessionResponseSchema.parse(json);
}

export async function sendAdvisorMessage(
  threadId: string,
  request: ChatMessageRequest,
  handlers: AdvisorSseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  if (appEnv.advisorMock) {
    await sendMockAdvisorMessage(request.message, handlers);
    return;
  }

  const res = await fetch(`${appEnv.advisorApiBase}/v1/threads/${threadId}/messages`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
    body: JSON.stringify(request),
    signal,
  });

  if (!res.ok || !res.body) {
    throw new Error(`Chat request failed (${res.status})`);
  }

  for await (const { event, data } of parseSseStream(res.body)) {
    await dispatchSseEvent(event, data, handlers);
  }
}
