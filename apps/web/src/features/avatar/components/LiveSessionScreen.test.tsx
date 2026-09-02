import { describe, expect, it, vi, beforeEach } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { LiveSessionRoute } from './LiveSessionScreen';
import { createSandboxSessionToken } from '@/services/liveavatar-service';
import { setLocale } from '@/i18n';
import * as HeyGenSDK from '@heygen/liveavatar-web-sdk';

vi.mock('@heygen/liveavatar-web-sdk', async () => await import('@/test/liveavatar-sdk-stub'));

const { mockAppEnv } = vi.hoisted(() => ({
  mockAppEnv: { liveAvatarUiOnly: false, advisorMock: true },
}));

vi.mock('@/config/env', () => ({
  appEnv: mockAppEnv,
}));

const { __emitEvent } = HeyGenSDK as unknown as {
  __emitEvent: (event: string, payload: unknown) => void;
};

vi.mock('@/services/liveavatar-service', () => ({
  createSandboxSessionToken: vi.fn(),
}));

describe('LiveSessionRoute', () => {
  beforeEach(() => {
    mockAppEnv.liveAvatarUiOnly = false;
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
    expect(screen.getByRole('heading', { name: 'Habla con Tino' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Iniciar conversación' })).toBeInTheDocument();
  });

  it('starts a session after minting a sandbox token', async () => {
    vi.mocked(createSandboxSessionToken).mockResolvedValue('sandbox-token');
    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    expect(await screen.findByText('Conectando...')).toBeInTheDocument();
    expect(await screen.findByRole('region', { name: 'Consulta con Tino' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Terminar' })).toBeInTheDocument();
    expect(createSandboxSessionToken).toHaveBeenCalledTimes(1);
  });

  it('shows a compact loading state while the live session connects', async () => {
    vi.mocked(createSandboxSessionToken).mockResolvedValue('sandbox-token');
    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));
    expect(await screen.findByText('Conectando...')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Consulta con Tino' })).toBeInTheDocument();
    expect(screen.queryByLabelText('Mensaje para el avatar')).not.toBeInTheDocument();
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
    await screen.findByText('Conectando...');
    act(() => {
      __emitEvent('SESSION_STATE_CHANGED', 'CONNECTED');
    });
    expect(await screen.findByRole('status')).toHaveTextContent('Micrófono no disponible');
    expect(screen.getByLabelText('Mensaje para el avatar')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Silenciar micro' })).not.toBeInTheDocument();
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

  it('renders copy in english when the locale changes', () => {
    setLocale('en');
    render(<LiveSessionRoute />);
    expect(screen.getByRole('heading', { name: 'Talk with Tino' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Start conversation' })).toBeInTheDocument();
  });

  it('opens the live UI without minting a sandbox token when ui-only mode is on', async () => {
    mockAppEnv.liveAvatarUiOnly = true;

    render(<LiveSessionRoute />);
    fireEvent.click(screen.getByRole('button', { name: 'Iniciar conversación' }));

    expect(await screen.findByRole('region', { name: 'Consulta con Tino' })).toBeInTheDocument();
    expect(screen.getByLabelText('Mensaje para el avatar')).toBeInTheDocument();
    expect(createSandboxSessionToken).not.toHaveBeenCalled();
  });
});
