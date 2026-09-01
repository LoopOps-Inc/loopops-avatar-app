import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useLiveAvatarSession } from './use-liveavatar-session';
import { SessionDisconnectReason, SessionEvent } from '@heygen/liveavatar-web-sdk';
import * as sdk from '@heygen/liveavatar-web-sdk';

type Listener = (...args: unknown[]) => void;

const listeners = new Map<string, Listener>();

vi.mock('@heygen/liveavatar-web-sdk', () => {
  const SessionState = {
    INACTIVE: 'INACTIVE',
    CONNECTING: 'CONNECTING',
    CONNECTED: 'CONNECTED',
    DISCONNECTING: 'DISCONNECTING',
    DISCONNECTED: 'DISCONNECTED',
  } as const;
  const SessionDisconnectReason = {
    UNKNOWN_REASON: 'UNKNOWN_REASON',
    CLIENT_INITIATED: 'CLIENT_INITIATED',
    SESSION_START_FAILED: 'SESSION_START_FAILED',
    SERVER_INITIATED: 'SERVER_INITIATED',
  } as const;
  const SessionEvent = {
    SESSION_STATE_CHANGED: 'SESSION_STATE_CHANGED',
    SESSION_STREAM_READY: 'SESSION_STREAM_READY',
    SESSION_CONNECTION_QUALITY_CHANGED: 'SESSION_CONNECTION_QUALITY_CHANGED',
    SESSION_DISCONNECTED: 'SESSION_DISCONNECTED',
  } as const;
  const ConnectionQuality = {
    UNKNOWN: 'UNKNOWN',
    GOOD: 'GOOD',
    POOR: 'POOR',
    LOST: 'LOST',
  } as const;

  class LiveAvatarSession {
    voiceChat = {
      isMuted: false,
      mute: vi.fn(async () => {
        this.voiceChat.isMuted = true;
      }),
      unmute: vi.fn(async () => {
        this.voiceChat.isMuted = false;
      }),
    };
    constructor(
      public readonly token: string,
      public readonly config?: { voiceChat?: boolean },
    ) {}
    on = vi.fn((event: string, listener: Listener) => {
      listeners.set(event, listener);
    });
    removeAllListeners = vi.fn(() => listeners.clear());
    start = vi.fn().mockResolvedValue(undefined);
    stop = vi.fn().mockResolvedValue(undefined);
    attach = vi.fn();
    message = vi.fn().mockReturnValue('evt-1');
    interrupt = vi.fn();
    keepAlive = vi.fn().mockResolvedValue(undefined);
  }

  let __lastInstance: LiveAvatarSession | null = null;
  const ProxiedSession = class extends LiveAvatarSession {
    constructor(...args: [] | [string, { voiceChat?: boolean }]) {
      super(args[0] ?? '', args[1]);
      // eslint-disable-next-line @typescript-eslint/no-this-alias
      __lastInstance = this;
    }
  };
  return {
    SessionState,
    SessionDisconnectReason,
    SessionEvent,
    ConnectionQuality,
    AgentEventsEnum: {
      USER_SPEAK_STARTED: 'USER_SPEAK_STARTED',
      USER_SPEAK_ENDED: 'USER_SPEAK_ENDED',
      AVATAR_SPEAK_STARTED: 'AVATAR_SPEAK_STARTED',
      AVATAR_SPEAK_ENDED: 'AVATAR_SPEAK_ENDED',
      USER_TRANSCRIPTION_CHUNK: 'USER_TRANSCRIPTION_CHUNK',
      AVATAR_TRANSCRIPTION_CHUNK: 'AVATAR_TRANSCRIPTION_CHUNK',
      USER_TRANSCRIPTION: 'USER_TRANSCRIPTION',
      AVATAR_TRANSCRIPTION: 'AVATAR_TRANSCRIPTION',
    },
    LiveAvatarSession: ProxiedSession,
    __getLastInstance: () => __lastInstance,
  };
});

type MockSessionInstance = {
  config?: { voiceChat?: boolean };
  voiceChat: { mute: ReturnType<typeof vi.fn>; unmute: ReturnType<typeof vi.fn> };
};

function getLastInstance(): MockSessionInstance {
  return (sdk as unknown as { __getLastInstance: () => MockSessionInstance }).__getLastInstance();
}

function emit(event: string, payload?: unknown) {
  act(() => {
    listeners.get(event)?.(payload);
  });
}

describe('useLiveAvatarSession', () => {
  beforeEach(() => {
    listeners.clear();
    vi.clearAllMocks();
  });

  it('creates the session with voiceChat=false by default', () => {
    renderHook(() => useLiveAvatarSession('token-1'));
    expect(getLastInstance().config?.voiceChat).toBe(false);
  });

  it('creates the session with voiceChat=true when requested', () => {
    renderHook(() => useLiveAvatarSession('token-1', { voiceChat: true }));
    expect(getLastInstance().config?.voiceChat).toBe(true);
  });

  it('maps SESSION_DISCONNECTED SERVER_INITIATED to endReason "server"', () => {
    const { result } = renderHook(() => useLiveAvatarSession('token-1'));
    emit(SessionEvent.SESSION_DISCONNECTED, SessionDisconnectReason.SERVER_INITIATED);
    expect(result.current.endReason).toBe('server');
  });

  it('maps user stop() to endReason "user"', async () => {
    const { result } = renderHook(() => useLiveAvatarSession('token-1'));
    await act(async () => {
      await result.current.stop();
    });
    emit(SessionEvent.SESSION_DISCONNECTED, SessionDisconnectReason.CLIENT_INITIATED);
    expect(result.current.endReason).toBe('user');
  });

  it('maps SESSION_START_FAILED to endReason "error"', () => {
    const { result } = renderHook(() => useLiveAvatarSession('token-1'));
    emit(SessionEvent.SESSION_DISCONNECTED, SessionDisconnectReason.SESSION_START_FAILED);
    expect(result.current.endReason).toBe('error');
  });

  it('mutes the mic while the avatar talks and unmutes after (voice sessions)', async () => {
    renderHook(() => useLiveAvatarSession('token-1', { voiceChat: true }));
    const instance = getLastInstance();
    emit('AVATAR_SPEAK_STARTED');
    await act(async () => {});
    expect(instance.voiceChat.mute).toHaveBeenCalled();
    emit('AVATAR_SPEAK_ENDED');
    await act(async () => {});
    expect(instance.voiceChat.unmute).toHaveBeenCalled();
  });

  it('does not auto-unmute when the user muted manually', async () => {
    const { result } = renderHook(() => useLiveAvatarSession('token-1', { voiceChat: true }));
    const instance = getLastInstance();
    act(() => {
      result.current.setMicMuted(true);
    });
    await act(async () => {});
    emit('AVATAR_SPEAK_STARTED');
    emit('AVATAR_SPEAK_ENDED');
    await act(async () => {});
    expect(instance.voiceChat.unmute).not.toHaveBeenCalled();
  });

  it('builds chat messages from transcription events (cumulative user, appended avatar)', () => {
    const { result } = renderHook(() => useLiveAvatarSession('token-1'));
    emit('USER_TRANSCRIPTION_CHUNK', { text: 'Hola' });
    emit('USER_TRANSCRIPTION_CHUNK', { text: 'Hola, cómo' });
    emit('AVATAR_TRANSCRIPTION_CHUNK', { text: '¡Hola' });
    emit('AVATAR_TRANSCRIPTION_CHUNK', { text: '!' });
    expect(result.current.messages).toEqual([
      { sender: 'user', message: 'Hola, cómo', timestamp: expect.any(Number) },
      { sender: 'avatar', message: '¡Hola!', timestamp: expect.any(Number) },
    ]);
  });
});
