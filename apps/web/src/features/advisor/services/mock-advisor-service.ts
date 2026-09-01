import type { AdvisorService, AdvisorStreamEvent } from '../types';
import { INTENT_PATTERNS, MOCK_TURNS, type MockTurn } from './mock-advisor-fixtures';

type CreateMockAdvisorServiceOptions = {
  /** Delay between streamed events. Set 0 in tests. */
  delayMs?: number;
};

function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/\p{Diacritic}/gu, '');
}

function matchIntent(message: string): MockTurn {
  const normalized = normalize(message);
  const intent = INTENT_PATTERNS.find(({ pattern }) => pattern.test(normalized));
  return intent ? intent.turn : MOCK_TURNS.fallback;
}

function chunkSpeech(speech: string): string[] {
  return speech.match(/[^ ]+(?: [^ ]+)*/g) ?? [];
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Frontend mock of the advisor backend: fixtures mirror the mock tools in
 * apps/agent/README.md and honor the split-channel invariant (exact figures
 * live in ui_payload only, never in speech). When the real API lands, an
 * SSE-backed AdvisorService replaces this implementation with the same shape.
 */
export function createMockAdvisorService(
  options: CreateMockAdvisorServiceOptions = {},
): AdvisorService {
  const delayMs = options.delayMs ?? 40;
  let turnCount = 0;

  async function* streamTurn(turn: MockTurn): AsyncIterable<AdvisorStreamEvent> {
    turnCount += 1;
    for (const chunk of chunkSpeech(turn.speech)) {
      yield { event: 'token', data: { text: `${chunk} ` } };
      if (delayMs > 0) await sleep(delayMs);
    }
    for (const ui of turn.uiPayload) {
      yield { event: 'ui', data: ui };
      if (delayMs > 0) await sleep(delayMs);
    }
    yield {
      event: 'done',
      data: {
        turn_id: `mock-turn-${turnCount}`,
        evidence_id: 'mock-evidence',
        service_type: 'no_asesorado',
      },
    };
  }

  return {
    sendTurn: (message) => streamTurn(matchIntent(message)),
    sendGreeting: () => streamTurn(MOCK_TURNS.greeting),
  };
}
