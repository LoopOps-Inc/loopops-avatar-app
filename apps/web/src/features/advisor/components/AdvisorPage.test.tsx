import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdvisorRoute } from './AdvisorPage';
import { createAdvisorSession } from '@/services/advisor-service';
import { createSandboxSessionToken } from '@/services/liveavatar-service';
import { createMockAdvisorSession } from '@/services/advisor-mock';
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

vi.mock('@/services/advisor-service', () => ({
  createAdvisorSession: vi.fn(),
  sendAdvisorMessage: vi.fn(),
}));

vi.mock('@/services/liveavatar-service', () => ({
  createSandboxSessionToken: vi.fn(),
}));

const mockSession = createMockAdvisorSession();

describe('AdvisorRoute', () => {
  beforeEach(() => {
    vi.mocked(createAdvisorSession).mockReset();
    vi.mocked(createSandboxSessionToken).mockReset();
    vi.mocked(createAdvisorSession).mockResolvedValue(mockSession);
    setLocale('es');
  });

  it('renders the advisor screen after session loads', async () => {
    render(<AdvisorRoute />);

    expect(await screen.findByText(/Rodrigo/i)).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Video' })).toBeInTheDocument();
  });

  it('starts a sandbox avatar session when video mode is selected', async () => {
    vi.mocked(createSandboxSessionToken).mockResolvedValue('sandbox-token');

    render(<AdvisorRoute />);
    await screen.findByText(/Rodrigo/i);

    fireEvent.click(screen.getByRole('radio', { name: 'Video' }));

    await waitFor(() => {
      expect(createSandboxSessionToken).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText('Conectando...')).toBeInTheDocument();
  });
});
