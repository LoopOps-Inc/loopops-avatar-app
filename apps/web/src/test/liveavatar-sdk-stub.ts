import { vi } from 'vitest';

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

const AgentEventsEnum = {
  USER_SPEAK_STARTED: 'USER_SPEAK_STARTED',
  USER_SPEAK_ENDED: 'USER_SPEAK_ENDED',
  AVATAR_SPEAK_STARTED: 'AVATAR_SPEAK_STARTED',
  AVATAR_SPEAK_ENDED: 'AVATAR_SPEAK_ENDED',
  USER_TRANSCRIPTION_CHUNK: 'USER_TRANSCRIPTION_CHUNK',
  AVATAR_TRANSCRIPTION_CHUNK: 'AVATAR_TRANSCRIPTION_CHUNK',
  USER_TRANSCRIPTION: 'USER_TRANSCRIPTION',
  AVATAR_TRANSCRIPTION: 'AVATAR_TRANSCRIPTION',
} as const;

const listeners: Array<{ event: string; handler: (payload: unknown) => void }> = [];

class LiveAvatarSession {
  voiceChat = { isMuted: false, mute: vi.fn(async () => {}), unmute: vi.fn(async () => {}) };
  on = vi.fn((event: string, handler: (payload: unknown) => void) => {
    listeners.push({ event, handler });
  });
  removeAllListeners = vi.fn();
  start = vi.fn().mockResolvedValue(undefined);
  stop = vi.fn().mockResolvedValue(undefined);
  attach = vi.fn();
  message = vi.fn().mockReturnValue('evt-1');
  interrupt = vi.fn();
  keepAlive = vi.fn().mockResolvedValue(undefined);
}

/** Fire a session event into every registered handler (test helper). */
export const __emitEvent = (event: string, payload: unknown) => {
  listeners
    .filter((listener) => listener.event === event)
    .forEach((listener) => listener.handler(payload));
};

export {
  AgentEventsEnum,
  ConnectionQuality,
  LiveAvatarSession,
  SessionDisconnectReason,
  SessionEvent,
  SessionState,
};
