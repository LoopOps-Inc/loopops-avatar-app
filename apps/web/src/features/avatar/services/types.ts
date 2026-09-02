import type {
  SseCitationsEvent,
  SseDoneEvent,
  SseErrorEvent,
  SseTokenEvent,
  UIComponent,
} from '@loopops/contracts';

export type AdvisorStreamEvent =
  | { event: 'token'; data: SseTokenEvent }
  | { event: 'ui'; data: UIComponent }
  | { event: 'citations'; data: SseCitationsEvent }
  | { event: 'error'; data: SseErrorEvent }
  | { event: 'done'; data: SseDoneEvent };

export interface AdvisorService {
  sendTurn(message: string): AsyncIterable<AdvisorStreamEvent>;
}
