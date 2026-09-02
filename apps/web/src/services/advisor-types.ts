import type {
  SseCitationsEvent,
  SseDoneEvent,
  SseErrorEvent,
  SseFormSpecEvent,
  UIComponent,
} from '@loopops/contracts';

export type AdvisorSseHandlers = {
  onToken: (chunk: string) => void;
  onUi: (component: UIComponent) => void;
  onCitations: (citations: SseCitationsEvent) => void;
  onFormSpec: (form: SseFormSpecEvent) => void;
  onError: (error: SseErrorEvent) => void;
  onDone: (done: SseDoneEvent) => void;
};
