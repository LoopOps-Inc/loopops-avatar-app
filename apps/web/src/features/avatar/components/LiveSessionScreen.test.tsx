import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { LiveSessionRoute } from './LiveSessionScreen';
import { createSandboxSessionToken } from '@/services/liveavatar-service';
import { setLocale } from '@/i18n';
import * as HeyGenSDK from '@heygen/liveavatar-web-sdk';

const { __emitEvent } = HeyGenSDK as unknown as {
  __emitEvent: (event: string, payload: unknown) => void;
};

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

  const __emitEvent = (event: string, payload: unknown) => {
    listeners
      .filter((listener) => listener.event === event)
      .forEach((listener) => listener.handler(payload));
  };

  return {
    SessionState,
    SessionDisconnectReason,
    SessionEvent,
    ConnectionQuality,
    AgentEventsEnum,
    LiveAvatarSession,
    __emitEvent,
  };
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
    // SnapSheet measures the frame via clientHeight, always 0 in jsdom.
    vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(800);
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
    expect(await screen.findByRole('region', { name: 'Tu asesor Actinver' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Terminar' })).toBeInTheDocument();
    expect(createSandboxSessionToken).toHaveBeenCalledTimes(1);
  });

  it('toggles the sheet between chat and full screen snaps', async () => {
    vi.mocked(createSandboxSessionToken).mockResolvedValue('sandbox-token');
    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    await screen.findByText('Conectando...');
    act(() => {
      __emitEvent('SESSION_STATE_CHANGED', 'CONNECTED');
    });
    const expand = await screen.findByRole('button', { name: 'Pantalla completa' });
    fireEvent.click(expand);
    expect(screen.getByRole('button', { name: 'Salir de pantalla completa' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Salir de pantalla completa' }));
    expect(screen.getByRole('button', { name: 'Pantalla completa' })).toBeInTheDocument();
  });

  it('shows the error message when the token request fails', async () => {
    vi.mocked(createSandboxSessionToken).mockRejectedValue(new Error('boom'));
    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    expect(await screen.findByText('boom')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Iniciar conversación' })).toBeInTheDocument();
  });

  it('shows a compact loading state while the live session connects', async () => {
    vi.mocked(createSandboxSessionToken).mockResolvedValue('sandbox-token');
    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    expect(await screen.findByText('Conectando...')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Tu asesor Actinver' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Mensaje para el avatar')).not.toBeInTheDocument();
  });

  it('starts a typing-only session with a notice when mic permission is denied', async () => {
    Object.defineProperty(window.navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error('denied')) },
    });
    vi.mocked(createSandboxSessionToken).mockResolvedValue('sandbox-token');
    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    await screen.findByText('Conectando...');
    act(() => {
      __emitEvent('SESSION_STATE_CHANGED', 'CONNECTED');
    });
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
