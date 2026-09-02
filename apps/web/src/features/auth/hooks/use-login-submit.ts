import { useState } from 'react';
import { useNavigate } from '@tanstack/react-router';
import { useTranslation } from '@/i18n';
import { ApiError, mintDevToken } from '@/services/advisor-service';
import { setDevAuth } from '@/services/dev-auth';

const DIGIT_CLIENT_ID = /^\d+$/;

function mapMintError(code: string | undefined, translate: (key: string) => string): string {
  if (code === 'UNAUTHENTICATED') return translate('auth.error_unauthenticated');
  if (code === 'VALIDATION_ERROR') return translate('auth.error_validation');
  return translate('auth.error_unknown');
}

export function useLoginSubmit() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [clientId, setClientId] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    const trimmedId = clientId.trim();
    const trimmedPassword = password.trim();
    if (!trimmedId || !trimmedPassword) return;
    if (!DIGIT_CLIENT_ID.test(trimmedId)) {
      setError(t('auth.client_id_invalid'));
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const token = await mintDevToken(trimmedId, trimmedPassword);
      setDevAuth({
        clientId: token.client_id,
        accessToken: token.access_token,
        expiresAt: Date.now() + token.expires_in * 1000,
      });
      setPassword('');
      await navigate({ to: '/demo' });
    } catch (err) {
      setError(mapMintError(err instanceof ApiError ? err.code : undefined, t));
    } finally {
      setSubmitting(false);
    }
  };

  return {
    clientId,
    setClientId,
    password,
    setPassword,
    error,
    submitting,
    submit,
  };
}
