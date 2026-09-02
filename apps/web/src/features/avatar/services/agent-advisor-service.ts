import { getLocale } from '@/i18n';
import type { AdvisorSseHandlers } from '@/services/advisor-types';
import { sendAdvisorMessage } from '@/services/advisor-service';
import type { AdvisorService, AdvisorStreamEvent } from './types';

async function* streamEvents(
  run: (handlers: AdvisorSseHandlers) => Promise<void>,
): AsyncGenerator<AdvisorStreamEvent> {
  const queue: AdvisorStreamEvent[] = [];
  let notify: (() => void) | null = null;
  let failure: unknown = null;
  let finished = false;

  const push = (event: AdvisorStreamEvent) => {
    queue.push(event);
    notify?.();
    notify = null;
  };

  void run({
    onToken: (text) => push({ event: 'token', data: { text } }),
    onUi: (component) => push({ event: 'ui', data: component }),
    onCitations: (citations) => push({ event: 'citations', data: citations }),
    onFormSpec: () => {},
    onError: (error) => push({ event: 'error', data: error }),
    onDone: (done) => push({ event: 'done', data: done }),
  })
    .catch((err: unknown) => {
      failure = err;
    })
    .finally(() => {
      finished = true;
      notify?.();
      notify = null;
    });

  while (true) {
    const next = queue.shift();
    if (next) {
      yield next;
      continue;
    }
    if (finished) {
      if (failure) throw failure;
      return;
    }
    await new Promise<void>((resolve) => {
      notify = resolve;
    });
  }
}

export function createAgentAdvisorService(threadId: string): AdvisorService {
  return {
    sendTurn: (message) =>
      streamEvents((handlers) =>
        sendAdvisorMessage(
          threadId,
          { text: message, locale: getLocale(), client_turn_id: crypto.randomUUID() },
          handlers,
        ),
      ),
  };
}
