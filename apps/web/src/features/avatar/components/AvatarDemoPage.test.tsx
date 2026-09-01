import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { AvatarDemoRoute } from './AvatarDemoPage';
import { createSandboxSessionToken } from '@/services/liveavatar-service';
import { setLocale } from '@/i18n';

vi.mock('@heygen/liveavatar-web-sdk', () => {
  const SessionState = {
    INACTIVE: 'INACTIVE',
    CONNECTING: 'CONNECTING',
    CONNECTED: 'CONNECTED',
    DISCONNECTED: 'DISCONNECTED',
  } as const;
  const ConnectionQuality = {
    UNKNOWN: 'UNKNOWN',
    GOOD: 'GOOD',
    POOR: 'POOR',
    LOST: 'LOST',
  } as const;
  const SessionEvent = {
    SESSION_STATE_CHANGED: 'SESSION_STATE_CHANGED',
    SESSION_STREAM_READY: 'SESSION_STREAM_READY',
    SESSION_CONNECTION_QUALITY_CHANGED: 'SESSION_CONNECTION_QUALITY_CHANGED',
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
    on = vi.fn();
    removeAllListeners = vi.fn();
    start = vi.fn().mockResolvedValue(undefined);
    stop = vi.fn().mockResolvedValue(undefined);
    attach = vi.fn();
    message = vi.fn().mockResolvedValue(undefined);
    repeat = vi.fn();
    interrupt = vi.fn();
    keepAlive = vi.fn().mockResolvedValue(undefined);
  }

  return { SessionState, ConnectionQuality, SessionEvent, AgentEventsEnum, LiveAvatarSession };
});

vi.mock('@/services/liveavatar-service', () => ({
  createSandboxSessionToken: vi.fn(),
}));

describe('AvatarDemoRoute', () => {
  beforeEach(() => {
    vi.mocked(createSandboxSessionToken).mockReset();
    setLocale('es');
  });

  it('renders the sandbox start screen', () => {
    render(<AvatarDemoRoute />);

    expect(screen.getByRole('heading', { name: 'Demo LiveAvatar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Iniciar sandbox' })).toBeInTheDocument();
  });

  it('starts a session panel after minting a sandbox token', async () => {
    vi.mocked(createSandboxSessionToken).mockResolvedValue('sandbox-token');

    render(<AvatarDemoRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar sandbox' }));

    expect(await screen.findByText('Conectando...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Terminar' })).toBeInTheDocument();
    expect(createSandboxSessionToken).toHaveBeenCalledTimes(1);
  });

  it('shows the error message when the token request fails', async () => {
    vi.mocked(createSandboxSessionToken).mockRejectedValue(new Error('boom'));

    render(<AvatarDemoRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar sandbox' }));

    expect(await screen.findByText('boom')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Iniciar sandbox' })).toBeInTheDocument();
  });

  it('renders copy in english when the locale changes', () => {
    setLocale('en');

    render(<AvatarDemoRoute />);

    expect(screen.getByRole('heading', { name: 'LiveAvatar Demo' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start sandbox' })).toBeInTheDocument();
  });
});
