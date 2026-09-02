import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import type { AvatarSessionResponse, SessionResponse } from '@loopops/contracts';
import { LiveSessionRoute } from './LiveSessionScreen';
import {
  ackFirstTurnDisclosures,
  ackVoiceConsent,
  createAdvisorSession,
  createAvatarSession,
  mintDevToken,
} from '@/services/advisor-service';
import { clearDevAuth, getDevAuth, setDevAuth } from '@/services/dev-auth';
import { setLocale } from '@/i18n';

const navigateMock = vi.fn();

vi.mock('@tanstack/react-router', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@tanstack/react-router')>();
  return {
    ...actual,
    useNavigate: () => navigateMock,
  };
});

const stubState = vi.hoisted(() => {
  const state = {
    sessionState: 'INACTIVE' as 'INACTIVE' | 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED',
    endReason: null as 'user' | 'server' | 'error' | null,
  };
  const listeners = new Set<() => void>();
  return {
    state,
    set: (patch: Partial<typeof state>) => {
      Object.assign(state, patch);
      listeners.forEach((listener) => listener());
    },
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
    snapshot: () => `${state.sessionState}:${state.endReason}`,
  };
});

vi.mock('@/services/advisor-service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/advisor-service')>();
  return {
    ...actual,
    createAdvisorSession: vi.fn(),
    ackFirstTurnDisclosures: vi.fn(),
    ackVoiceConsent: vi.fn(),
    createAvatarSession: vi.fn(),
    stopAvatarSession: vi.fn(),
    sendAdvisorMessage: vi.fn(),
    listInvestors: vi.fn(),
    mintDevToken: vi.fn(),
  };
});

vi.mock('../hooks/use-liveavatar-session', async () => {
  const { useSyncExternalStore } = await import('react');
  return {
    useLiveAvatarSession: () => {
      useSyncExternalStore(stubState.subscribe, stubState.snapshot, stubState.snapshot);
      return {
        sessionState: stubState.state.sessionState,
        isStreamReady: stubState.state.sessionState === 'CONNECTED',
        connectionQuality: 'GOOD',
        isUserTalking: false,
        isAvatarTalking: false,
        isMicMuted: true,
        micError: false,
        endReason: stubState.state.endReason,
        videoRef: { current: null },
        start: async () => {},
        stop: async () => {},
        attach: () => {},
        sendMessage: () => '',
        repeat: () => {},
        interrupt: () => {},
        keepAlive: async () => {},
        setMicMuted: () => {},
        speak: () => {},
        unlockPlayback: async () => true,
      };
    },
  };
});

const advisorSession = {
  thread_id: 'thread-1',
  thread_started_at: '2026-08-02T04:00:00.000Z',
  client: { first_name: 'Mariano', risk_category: 'Agresivo' },
} as SessionResponse;

const avatarSession = {
  avatar_session_id: 'avatar-1',
  livekit_url: 'wss://livekit.example',
  livekit_client_token: 'token',
  max_session_duration_s: 600,
  expires_at: new Date().toISOString(),
  audio_ws_path: '/ws/avatar',
} as AvatarSessionResponse;

async function startSession() {
  vi.mocked(createAdvisorSession).mockResolvedValue(advisorSession);
  vi.mocked(ackFirstTurnDisclosures).mockResolvedValue(undefined);
  vi.mocked(ackVoiceConsent).mockResolvedValue(undefined);
  vi.mocked(createAvatarSession).mockResolvedValue(avatarSession);
  render(<LiveSessionRoute />);
  expect(await screen.findByText('Hola, Mariano')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
}

describe('LiveSessionRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    stubState.set({ sessionState: 'INACTIVE', endReason: null });
    clearDevAuth();
    Object.defineProperty(window.navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [] }) },
    });
    vi.spyOn(HTMLElement.prototype, 'clientHeight', 'get').mockReturnValue(800);
    sessionStorage.clear();
    setLocale('es');
    vi.mocked(createAdvisorSession).mockResolvedValue(advisorSession);
    vi.mocked(mintDevToken).mockResolvedValue({
      access_token: 'minted',
      client_id: '200001',
      expires_in: 900,
    });
  });

  it('renders the welcome screen with the client first name', async () => {
    render(<LiveSessionRoute />);
    expect(await screen.findByText('Hola, Mariano')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Habla con Tino' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Iniciar conversación' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
  });

  it('clears auth and returns to login when closing the session', async () => {
    setDevAuth({
      clientId: '200001',
      accessToken: 'tok',
      expiresAt: Date.now() + 60_000,
    });
    render(<LiveSessionRoute />);
    expect(await screen.findByText('Hola, Mariano')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Cerrar sesión' }));
    expect(getDevAuth()).toBeNull();
    expect(navigateMock).toHaveBeenCalledWith({ to: '/' });
  });

  it('starts a session through the advisor backend after the start action', async () => {
    await startSession();
    expect(await screen.findByText('Conectando...')).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Consulta con Tino' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Terminar' })).toBeInTheDocument();
    expect(createAdvisorSession).toHaveBeenCalledTimes(1);
    expect(mintDevToken).not.toHaveBeenCalled();
    expect(ackFirstTurnDisclosures).toHaveBeenCalledTimes(1);
    expect(ackVoiceConsent).toHaveBeenCalledTimes(1);
    expect(createAvatarSession).toHaveBeenCalledWith('thread-1', 'portrait');
  });

  it('does not mint when starting a session again after the server ends it', async () => {
    await startSession();
    await screen.findByText('Conectando...');
    act(() => {
      stubState.set({ endReason: 'server' });
    });
    expect(await screen.findByText('La sesión se cerró. Puedes iniciar otra.')).toBeInTheDocument();
    expect(screen.getByText('Hola, Mariano')).toBeInTheDocument();
    act(() => {
      stubState.set({ sessionState: 'INACTIVE', endReason: null });
    });
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    expect(await screen.findByText('Conectando...')).toBeInTheDocument();
    expect(mintDevToken).not.toHaveBeenCalled();
    expect(createAdvisorSession).toHaveBeenCalledTimes(2);
  });

  it('shows a compact loading state while the live session connects', async () => {
    await startSession();
    expect(await screen.findByText('Conectando...')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Consulta con Tino' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Mensaje para el avatar')).not.toBeInTheDocument();
  });

  it('shows the error message when the session creation fails', async () => {
    vi.mocked(createAdvisorSession).mockRejectedValue(new Error('boom'));
    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    expect(await screen.findByText('boom')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Iniciar conversación' })).toBeInTheDocument();
    expect(mintDevToken).not.toHaveBeenCalled();
  });

  it('starts a typing-only session with a notice when mic permission is denied', async () => {
    Object.defineProperty(window.navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error('denied')) },
    });
    await startSession();
    await screen.findByText('Conectando...');
    act(() => {
      stubState.set({ sessionState: 'CONNECTED' });
    });
    expect(await screen.findByRole('status')).toHaveTextContent('Micrófono no disponible');
    expect(screen.getByLabelText('Mensaje para el avatar')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Activar micro' })).not.toBeInTheDocument();
    expect(createAvatarSession).toHaveBeenCalledTimes(1);
    expect(mintDevToken).not.toHaveBeenCalled();
  });

  it('returns to the start screen with a notice when the server ends the session', async () => {
    await startSession();
    await screen.findByText('Conectando...');
    act(() => {
      stubState.set({ endReason: 'server' });
    });
    expect(await screen.findByText('La sesión se cerró. Puedes iniciar otra.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Iniciar conversación' })).toBeInTheDocument();
  });

  it('renews the avatar session in place when it closes at max duration', async () => {
    vi.mocked(ackFirstTurnDisclosures).mockResolvedValue(undefined);
    vi.mocked(ackVoiceConsent).mockResolvedValue(undefined);
    vi.mocked(createAvatarSession).mockResolvedValue({
      ...avatarSession,
      max_session_duration_s: 0,
    });
    render(<LiveSessionRoute />);
    expect(await screen.findByText('Hola, Mariano')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    await screen.findByText('Conectando...');

    act(() => {
      stubState.set({ endReason: 'server' });
    });

    await vi.waitFor(() => {
      expect(createAvatarSession).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByRole('region', { name: 'Consulta con Tino' })).toBeInTheDocument();
    expect(screen.queryByText('La sesión se cerró. Puedes iniciar otra.')).not.toBeInTheDocument();
    expect(mintDevToken).not.toHaveBeenCalled();
  });

  it('toggles the sheet between chat and full screen snaps', async () => {
    await startSession();
    await screen.findByText('Conectando...');
    act(() => {
      stubState.set({ sessionState: 'CONNECTED' });
    });
    const expand = await screen.findByRole('button', { name: 'Pantalla completa' });
    fireEvent.click(expand);
    expect(screen.getByRole('button', { name: 'Salir de pantalla completa' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Salir de pantalla completa' }));
    expect(screen.getByRole('button', { name: 'Pantalla completa' })).toBeInTheDocument();
  });

  it('renders copy in english when the locale changes', async () => {
    setLocale('en');
    render(<LiveSessionRoute />);
    expect(await screen.findByText('Hi, Mariano')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Talk with Tino' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start conversation' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Close session' })).toBeInTheDocument();
  });
});
