import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { EmbedBridge } from './embed-bridge';
import { EMBED_BRIDGE_VERSION } from '@loopops/contracts';

function fakeWindow({ parent, originParam }: { parent?: Window; originParam?: string } = {}) {
  const win = {
    parent: parent ?? ({} as Window),
    location: {
      href: originParam ? `https://app.example/?origin=${originParam}` : 'https://app.example/',
    },
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  } as unknown as Window;
  return win;
}

describe('EmbedBridge', () => {
  beforeEach(() => {
    vi.spyOn(console, 'warn').mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('is a no-op when not embedded (window.parent === window)', () => {
    const win = fakeWindow();
    (win as unknown as { parent: Window }).parent = win;
    const bridge = new EmbedBridge(win);
    const handler = vi.fn();
    bridge.start(handler);
    expect(() => bridge.emit({ type: 'error', payload: { message: 'x' } })).not.toThrow();
    expect(handler).not.toHaveBeenCalled();
    bridge.dispose();
  });

  it('is disabled when embedded but no ?origin= param is present (fail closed)', () => {
    const win = fakeWindow({ parent: {} as Window });
    const bridge = new EmbedBridge(win);
    const postMessage = vi.fn();
    (win.parent as unknown as { postMessage: unknown }).postMessage = postMessage;
    bridge.emit({ type: 'error', payload: { message: 'x' } });
    expect(postMessage).not.toHaveBeenCalled();
  });

  it('emits validated envelopes to the host with the configured origin', () => {
    const win = fakeWindow({ parent: {} as Window, originParam: 'https://host.example' });
    const postMessage = vi.fn();
    (win.parent as unknown as { postMessage: unknown }).postMessage = postMessage;
    const bridge = new EmbedBridge(win);
    bridge.emit({ type: 'sessionState', payload: { state: 'CONNECTED', quality: 'GOOD' } });
    expect(postMessage).toHaveBeenCalledTimes(1);
    const [payload, targetOrigin] = postMessage.mock.calls[0];
    expect(targetOrigin).toBe('https://host.example');
    expect(payload.version).toBe(EMBED_BRIDGE_VERSION);
    expect(payload.message).toEqual({
      type: 'sessionState',
      payload: { state: 'CONNECTED', quality: 'GOOD' },
    });
  });

  it('delivers valid host commands to the handler', () => {
    const win = fakeWindow({ parent: {} as Window, originParam: 'https://host.example' });
    const bridge = new EmbedBridge(win);
    const handler = vi.fn();
    bridge.start(handler);
    const listener = (win.addEventListener as ReturnType<typeof vi.fn>).mock.calls.find(
      ([type]) => type === 'message',
    )?.[1] as (event: { source: unknown; data: unknown }) => void;
    expect(listener).toBeDefined();
    listener({
      source: win.parent,
      data: { version: EMBED_BRIDGE_VERSION, ts: 1, message: { type: 'stop' } },
    });
    expect(handler).toHaveBeenCalledWith({ type: 'stop' });
    bridge.dispose();
  });

  it('ignores messages from a different source window', () => {
    const win = fakeWindow({ parent: {} as Window, originParam: 'https://host.example' });
    const bridge = new EmbedBridge(win);
    const handler = vi.fn();
    bridge.start(handler);
    const listener = (win.addEventListener as ReturnType<typeof vi.fn>).mock.calls.find(
      ([type]) => type === 'message',
    )?.[1] as (event: { source: unknown; data: unknown }) => void;
    listener({
      source: {},
      data: { version: EMBED_BRIDGE_VERSION, ts: 1, message: { type: 'stop' } },
    });
    expect(handler).not.toHaveBeenCalled();
    bridge.dispose();
  });

  it('ignores unknown or malformed message types (forward compatible)', () => {
    const win = fakeWindow({ parent: {} as Window, originParam: 'https://host.example' });
    const bridge = new EmbedBridge(win);
    const handler = vi.fn();
    bridge.start(handler);
    const listener = (win.addEventListener as ReturnType<typeof vi.fn>).mock.calls.find(
      ([type]) => type === 'message',
    )?.[1] as (event: { source: unknown; data: unknown }) => void;
    listener({ source: win.parent, data: { version: 99, ts: 1, message: { type: 'stop' } } });
    listener({
      source: win.parent,
      data: { version: EMBED_BRIDGE_VERSION, ts: 1, message: { type: 'warp' } },
    });
    listener({ source: win.parent, data: 'not-an-object' });
    expect(handler).not.toHaveBeenCalled();
    bridge.dispose();
  });
});
