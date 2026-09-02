import type { FormEvent } from 'react';
import { AppShell } from '@/components/AppShell';
import { useTranslation } from '@/i18n';
import { getDevAuth } from '@/services/dev-auth';
import { useLoginSubmit } from '../hooks/use-login-submit';
import { SplashOverlay } from './SplashOverlay';

export function LoginScreen() {
  const { t } = useTranslation();
  const { clientId, setClientId, password, setPassword, error, submitting, submit } =
    useLoginSubmit();

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void submit();
  };

  return (
    <AppShell>
      <div className="bg-surface-sub flex min-h-dvh justify-center">
        <div className="bg-surface-sub sm:border-outline relative h-dvh w-full overflow-hidden sm:my-auto sm:h-[min(853px,calc(100dvh-3rem))] sm:max-w-md sm:rounded-lg sm:border">
          <SplashOverlay skip={Boolean(getDevAuth())} />
          <form
            onSubmit={handleSubmit}
            className="flex h-full flex-col justify-center gap-4 p-6"
          >
            <label htmlFor="auth-client-id" className="flex flex-col gap-1.5">
              <span className="text-content text-sm font-medium">{t('auth.client_id')}</span>
              <input
                id="auth-client-id"
                name="client_id"
                type="text"
                inputMode="numeric"
                autoComplete="username"
                value={clientId}
                onChange={(event) => setClientId(event.target.value)}
                disabled={submitting}
                className="border-outline bg-surface text-content min-h-11 w-full rounded-xs border px-3 text-sm focus:outline-none disabled:opacity-60"
              />
            </label>
            <label htmlFor="auth-password" className="flex flex-col gap-1.5">
              <span className="text-content text-sm font-medium">{t('auth.password')}</span>
              <input
                id="auth-password"
                name="password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                disabled={submitting}
                className="border-outline bg-surface text-content min-h-11 w-full rounded-xs border px-3 text-sm focus:outline-none disabled:opacity-60"
              />
            </label>
            {error && (
              <p
                role="alert"
                className="border-error/30 bg-error/10 text-error rounded-xs border px-4 py-3 text-sm"
              >
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={submitting}
              className="bg-filled-dark text-filled-dark-fg rounded-cta min-h-11 w-full cursor-pointer px-6 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60"
            >
              {t('auth.submit')}
            </button>
          </form>
        </div>
      </div>
    </AppShell>
  );
}
