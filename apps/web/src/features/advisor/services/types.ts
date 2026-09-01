import type {
  SseCitationsEvent,
  SseDoneEvent,
  SseTokenEvent,
  UIComponent,
} from '@loopops/contracts';

/** Event shape the real SSE client will emit (mirrors the chat contract). */
export type AdvisorStreamEvent =
  | { event: 'token'; data: SseTokenEvent }
  | { event: 'ui'; data: UIComponent }
  | { event: 'citations'; data: SseCitationsEvent }
  | { event: 'done'; data: SseDoneEvent };

export interface AdvisorService {
  sendTurn(message: string): AsyncIterable<AdvisorStreamEvent>;
  sendGreeting?(): AsyncIterable<AdvisorStreamEvent>;
}
