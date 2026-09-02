import { useCallback, useState } from 'react';
import type { AvatarSessionResponse } from '@loopops/contracts';
import { useTranslation } from '@/i18n';
import { ackVoiceConsent, createAvatarSession, stopAvatarSession } from '@/services/advisor-service';

export function useAdvisorAvatar() {
  const { t } = useTranslation();
  const [wantsAvatar, setWantsAvatar] = useState(false);
  const [session, setSession] = useState<AvatarSessionResponse | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [endedByServer, setEndedByServer] = useState(false);

  const turnOn = useCallback(
    async (threadId: string) => {
      if (starting || session) return;
      setStarting(true);
      setError(null);
      setEndedByServer(false);
      setWantsAvatar(true);
      try {
        await ackVoiceConsent();
        const created = await createAvatarSession(threadId, 'portrait');
        setSession(created);
      } catch (err) {
        setError(
          err instanceof Error && err.message
            ? `${t('advisor.avatar_error')} (${err.message})`
            : t('advisor.avatar_error'),
        );
        setWantsAvatar(false);
      } finally {
        setStarting(false);
      }
    },
    [session, starting, t],
  );

  const requestOff = useCallback(() => {
    setWantsAvatar(false);
    setSession((current) => {
      if (current) {
        void stopAvatarSession(current.avatar_session_id, 'user').catch(() => {});
      }
      return null;
    });
  }, []);

  const handleSessionEnded = useCallback((reason: 'user' | 'server') => {
    setSession(null);
    setWantsAvatar(false);
    if (reason === 'server') {
      setEndedByServer(true);
    }
  }, []);

  const toggle = useCallback(
    async (threadId: string) => {
      if (wantsAvatar || session) {
        requestOff();
        return;
      }
      await turnOn(threadId);
    },
    [wantsAvatar, session, requestOff, turnOn],
  );

  return {
    wantsAvatar,
    session,
    isActive: wantsAvatar && Boolean(session),
    starting,
    error,
    endedByServer,
    turnOn,
    requestOff,
    toggle,
    handleSessionEnded,
  };
}
