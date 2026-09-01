import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { LiveSessionRoute } from './LiveSessionScreen';
import { createSandboxSessionToken } from '@/services/liveavatar-service';
import { setLocale } from '@/i18n';

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

  class LiveAvatarSession {
    voiceChat = { isMuted: false, mute: vi.fn(async () => {}), unmute: vi.fn(async () => {}) };
    on = vi.fn();
    removeAllListeners = vi.fn();
    start = vi.fn().mockResolvedValue(undefined);
    stop = vi.fn().mockResolvedValue(undefined);
    attach = vi.fn();
    message = vi.fn().mockReturnValue('evt-1');
    interrupt = vi.fn();
    keepAlive = vi.fn().mockResolvedValue(undefined);
  }

  return { SessionState, SessionDisconnectReason, SessionEvent, ConnectionQuality, AgentEventsEnum, LiveAvatarSession };
});

vi.mock('@/services/liveavatar-service', () => ({
  createSandboxSessionToken: vi.fn(),
}));

describe('LiveSessionRoute', () => {
  beforeEach(() => {
    vi.mocked(createSandboxSessionToken).mockReset();
    Object.defineProperty(window.navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [] }) },
    });
    setLocale('es');
  });

  it('renders the welcome screen with a single start action', () => {
    render(<LiveSessionRoute />);
    expect(screen.getByRole('heading', { name: 'Tu asesor Actinver' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Iniciar conversación' })).toBeInTheDocument();
  });

  it('starts a session after minting a sandbox token', async () => {
    vi.mocked(createSandboxSessionToken).mockResolvedValue('sandbox-token');
    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    expect(await screen.findByText('Conectando...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Terminar' })).toBeInTheDocument();
    expect(createSandboxSessionToken).toHaveBeenCalledTimes(1);
  });

  it('shows the error message when the token request fails', async () => {
    vi.mocked(createSandboxSessionToken).mockRejectedValue(new Error('boom'));
    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    expect(await screen.findByText('boom')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Iniciar conversación' })).toBeInTheDocument();
  });

  it('starts a typing-only session with a notice when mic permission is denied', async () => {
    Object.defineProperty(window.navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error('denied')) },
    });
    vi.mocked(createSandboxSessionToken).mockResolvedValue('sandbox-token');
    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    expect(await screen.findByText('Conectando...')).toBeInTheDocument();
    expect(await screen.findByRole('status')).toHaveTextContent('Micrófono no disponible');
    expect(screen.getByLabelText('Mensaje para el avatar')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Silenciar micro' })).not.toBeInTheDocument();
    expect(createSandboxSessionToken).toHaveBeenCalledTimes(1);
  });

  it('renders copy in english when the locale changes', () => {
    setLocale('en');
    render(<LiveSessionRoute />);
    expect(screen.getByRole('heading', { name: 'Your Actinver advisor' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start conversation' })).toBeInTheDocument();
  });
});
