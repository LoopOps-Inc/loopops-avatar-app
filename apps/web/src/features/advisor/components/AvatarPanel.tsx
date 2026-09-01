import { useEffect, useRef } from 'react';
import { SessionState } from '@heygen/liveavatar-web-sdk';
import { useTranslation } from '@/i18n';
import { useLiveAvatarSession } from '@/features/avatar/hooks/use-liveavatar-session';
import { AvatarVideoSurface } from './AvatarVideoSurface';

export type AvatarSpeakFn = (text: string) => void;

type AvatarPanelProps = {
  sessionToken: string;
  active: boolean;
  onEnded: (reason: 'user' | 'server') => void;
  onSpeakReady?: (speak: AvatarSpeakFn | null) => void;
};

export function AvatarPanel({ sessionToken, active, onEnded, onSpeakReady }: AvatarPanelProps) {
  const { t } = useTranslation();
  const {
    sessionState,
    isStreamReady,
    connectionQuality,
    isAvatarTalking,
    start,
    stop,
    attach,
    repeat,
    interrupt,
    keepAlive,
  } = useLiveAvatarSession(sessionToken);

  const videoRef = useRef<HTMLVideoElement>(null);
  const userStoppedRef = useRef(false);

  useEffect(() => {
    if (sessionState === SessionState.DISCONNECTED) {
      onEnded(userStoppedRef.current ? 'user' : 'server');
    }
  }, [sessionState, onEnded]);

  useEffect(() => {
    if (sessionState === SessionState.INACTIVE) {
      void start();
    }
  }, [sessionState, start]);

  useEffect(() => {
    if (isStreamReady && videoRef.current) {
      attach(videoRef.current);
    }
  }, [attach, isStreamReady]);

  useEffect(() => {
    if (
      !active &&
      sessionState !== SessionState.DISCONNECTED &&
      sessionState !== SessionState.INACTIVE
    ) {
      userStoppedRef.current = true;
      void stop();
    }
  }, [active, sessionState, stop]);

  const handleClose = () => {
    userStoppedRef.current = true;
    void stop();
  };

  const isConnected = sessionState === SessionState.CONNECTED;

  useEffect(() => {
    if (!isConnected) {
      onSpeakReady?.(null);
      return;
    }
    onSpeakReady?.((text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      interrupt();
      repeat(trimmed);
    });
    return () => onSpeakReady?.(null);
  }, [interrupt, isConnected, onSpeakReady, repeat]);

  return (
    <AvatarVideoSurface
      videoRef={videoRef}
      sessionState={sessionState}
      isConnected={isConnected}
      connectionQuality={connectionQuality}
      isAvatarTalking={isAvatarTalking}
      onClose={handleClose}
      onInterrupt={() => void interrupt()}
      onKeepAlive={() => void keepAlive()}
      closeLabel={t('advisor.avatar_hide')}
      sandboxNotice={t('advisor.avatar_sandbox_notice')}
      variant="overlay"
    />
  );
}
