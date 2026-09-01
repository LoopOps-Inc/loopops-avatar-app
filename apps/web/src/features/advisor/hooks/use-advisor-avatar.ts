import { useCallback, useState } from 'react';
import { useTranslation } from '@/i18n';
import { createSandboxSessionToken } from '@/services/liveavatar-service';

type AvatarEndReason = 'user' | 'server';

export function useAdvisorAvatar() {
  const { t } = useTranslation();
  const [wantsAvatar, setWantsAvatar] = useState(false);
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [endedByServer, setEndedByServer] = useState(false);

  const turnOn = useCallback(async () => {
    if (starting || sessionToken) return;
    setStarting(true);
    setError(null);
    setEndedByServer(false);
    setWantsAvatar(true);
    try {
      const token = await createSandboxSessionToken();
      setSessionToken(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('demo.error_unknown'));
      setWantsAvatar(false);
    } finally {
      setStarting(false);
    }
  }, [sessionToken, starting, t]);

  const requestOff = useCallback(() => {
    setWantsAvatar(false);
  }, []);

  const handleSessionEnded = useCallback((reason: AvatarEndReason) => {
    setSessionToken(null);
    setWantsAvatar(false);
    if (reason === 'server') {
      setEndedByServer(true);
    }
  }, []);

  const toggle = useCallback(async () => {
    if (wantsAvatar || sessionToken) {
      requestOff();
      return;
    }
    await turnOn();
  }, [wantsAvatar, sessionToken, requestOff, turnOn]);

  return {
    wantsAvatar,
    sessionToken,
    isActive: wantsAvatar && Boolean(sessionToken),
    starting,
    error,
    endedByServer,
    turnOn,
    requestOff,
    toggle,
    handleSessionEnded,
  };
}
