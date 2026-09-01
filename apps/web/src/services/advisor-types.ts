import type { SseDoneEvent, SseErrorEvent, UIComponent } from '@loopops/contracts';

export type AdvisorSseHandlers = {
  onToken: (chunk: string) => void;
  onUi: (component: UIComponent) => void;
  onError: (error: SseErrorEvent) => void;
  onDone: (done: SseDoneEvent) => void;
};
