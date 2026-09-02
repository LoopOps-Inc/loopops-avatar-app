import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { LoginScreen } from './LoginScreen';
import { ApiError, mintDevToken } from '@/services/advisor-service';
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

vi.mock('@/services/advisor-service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/advisor-service')>();
  return {
    ...actual,
    mintDevToken: vi.fn(),
  };
});

function stubMatchMedia(reduced: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string) => ({
      matches: reduced && query.includes('prefers-reduced-motion'),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
      onchange: null,
    }),
  });
}

function fillCredentials(clientId: string, password: string) {
  fireEvent.change(screen.getByLabelText('Número de cliente'), { target: { value: clientId } });
  fireEvent.change(screen.getByLabelText('Contraseña'), { target: { value: password } });
}

describe('LoginScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    clearDevAuth();
    sessionStorage.clear();
    setLocale('es');
    stubMatchMedia(false);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('shows a timed splash overlay then the login form', async () => {
    vi.useFakeTimers();
    render(<LoginScreen />);

    const splash = screen.getByTestId('auth-splash');
    expect(splash).toBeInTheDocument();
    expect(splash).toHaveClass('bg-surface');
    expect(splash.querySelector('img')).toHaveAttribute(
      'src',
      expect.stringContaining('evaluar-test-media-bucket'),
    );
    expect(screen.getByLabelText('Número de cliente')).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(1500);
    });

    expect(screen.queryByTestId('auth-splash')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument();
  });

  it('skips the overlay when reduced motion is preferred', () => {
    stubMatchMedia(true);
    render(<LoginScreen />);

    expect(screen.queryByTestId('auth-splash')).not.toBeInTheDocument();
    expect(screen.getByTestId('auth-login-logo')).toHaveAttribute(
      'src',
      expect.stringContaining('evaluar-test-media-bucket'),
    );
    expect(screen.getByLabelText('Número de cliente')).toBeInTheDocument();
  });

  it('skips the overlay when a valid token is stored', () => {
    setDevAuth({
      clientId: '200001',
      accessToken: 'tok',
      expiresAt: Date.now() + 60_000,
    });
    render(<LoginScreen />);

    expect(screen.queryByTestId('auth-splash')).not.toBeInTheDocument();
  });

  it('mints with digit client_id 200001 and the entered password', async () => {
    stubMatchMedia(true);
    vi.mocked(mintDevToken).mockResolvedValue({
      access_token: 'tok',
      client_id: '200001',
      expires_in: 900,
    });
    render(<LoginScreen />);

    fillCredentials('200001', 'secret-pass');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    await waitFor(() => {
      expect(mintDevToken).toHaveBeenCalledWith('200001', 'secret-pass');
    });
  });

  it('rejects an alias ClientId without minting', async () => {
    stubMatchMedia(true);
    render(<LoginScreen />);

    fillCredentials('cl_demo_moderado', 'secret-pass');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(mintDevToken).not.toHaveBeenCalled();
    expect(await screen.findByRole('alert')).toHaveTextContent('Use solo números');
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument();
  });

  it('does not mint when ClientId or password is empty', () => {
    stubMatchMedia(true);
    render(<LoginScreen />);

    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(mintDevToken).not.toHaveBeenCalled();

    fillCredentials('200001', '');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));
    expect(mintDevToken).not.toHaveBeenCalled();
  });

  it('stores the token, opens the demo route, and does not persist the password', async () => {
    stubMatchMedia(true);
    vi.mocked(mintDevToken).mockResolvedValue({
      access_token: 'tok',
      client_id: '200001',
      expires_in: 900,
    });
    render(<LoginScreen />);

    fillCredentials('200001', 'secret-pass');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith({ to: '/demo' });
    });
    expect(getDevAuth()?.accessToken).toBe('tok');
    expect(getDevAuth()?.clientId).toBe('200001');
    expect(JSON.stringify(sessionStorage.getItem('actinver.dev-auth'))).not.toContain(
      'secret-pass',
    );
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument();
  });

  it('stays on login when mint fails', async () => {
    stubMatchMedia(true);
    vi.mocked(mintDevToken).mockRejectedValue(new ApiError('UNAUTHENTICATED', 'bad credentials'));
    render(<LoginScreen />);

    fillCredentials('200001', 'wrong');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Cliente o contraseña incorrectos');
    expect(navigateMock).not.toHaveBeenCalled();
    expect(getDevAuth()).toBeNull();
  });

  it('maps VALIDATION_ERROR to auth copy', async () => {
    stubMatchMedia(true);
    vi.mocked(mintDevToken).mockRejectedValue(new ApiError('VALIDATION_ERROR', 'invalid body'));
    render(<LoginScreen />);

    fillCredentials('200001', 'secret-pass');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Revise los datos e intente de nuevo',
    );
  });

  it('maps unknown mint errors to auth copy', async () => {
    stubMatchMedia(true);
    vi.mocked(mintDevToken).mockRejectedValue(new ApiError('RATE_LIMITED', 'slow down'));
    render(<LoginScreen />);

    fillCredentials('200001', 'secret-pass');
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'No se pudo iniciar sesión. Intente de nuevo.',
    );
  });
});
