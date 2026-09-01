import {
  EmbedCommandSchema,
  EmbedEnvelopeSchema,
  EMBED_BRIDGE_VERSION,
  type EmbedCommand,
  type EmbedEvent,
} from '@loopops/contracts';

export type EmbedCommandHandler = (command: EmbedCommand) => void;

/**
 * postMessage bridge between this app (running inside a native WebView) and
 * the host app. Standalone usage (no host, or missing ?origin= param) is a
 * no-op: the app works exactly the same in a plain browser tab.
 *
 * Host apps must load the URL with ?origin=<their origin> so events can be
 * posted with a pinned targetOrigin instead of '*'. Incoming commands are
 * accepted only from the parent window and must match the v1 envelope schema.
 */
export class EmbedBridge {
  private readonly parent: Window | null;
  private readonly targetOrigin: string | null = null;
  private readonly active: boolean;
  private handler: EmbedCommandHandler | null = null;
  private boundListener: ((event: MessageEvent) => void) | null = null;

  constructor(private readonly windowRef: Window) {
    const embedded = windowRef.parent !== windowRef;
    const originParam = new URL(windowRef.location.href).searchParams.get('origin');
    if (embedded && originParam) {
      this.parent = windowRef.parent;
      this.targetOrigin = originParam;
      this.active = true;
    } else {
      this.parent = null;
      this.active = false;
    }
  }

  get isActive(): boolean {
    return this.active;
  }

  start(handler: EmbedCommandHandler): () => void {
    if (!this.active || this.handler) return () => {};
    this.handler = handler;
    this.boundListener = (event: MessageEvent) => {
      if (event.source !== this.parent) return;
      const parsed = EmbedEnvelopeSchema.safeParse(event.data);
      if (!parsed.success) return;
      const command = EmbedCommandSchema.safeParse(parsed.data.message);
      if (!command.success) return;
      this.handler?.(command.data);
    };
    this.windowRef.addEventListener('message', this.boundListener);
    return () => this.dispose();
  }

  emit(event: EmbedEvent): void {
    if (!this.active || !this.parent || !this.targetOrigin) return;
    const envelope = { version: EMBED_BRIDGE_VERSION, ts: Date.now(), message: event };
    this.parent.postMessage(envelope, this.targetOrigin);
  }

  dispose(): void {
    if (this.boundListener) {
      this.windowRef.removeEventListener('message', this.boundListener);
      this.boundListener = null;
    }
    this.handler = null;
  }
}
