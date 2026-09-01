import { useCallback, useEffect, useRef } from 'react';
import { SessionState, type ConnectionQuality } from '@heygen/liveavatar-web-sdk';
import { useTranslation } from '@/i18n';
import { useLiveAvatarSession } from '@/features/avatar/hooks/use-liveavatar-session';
import { AvatarVideoSurface } from './AvatarVideoSurface';

export type AvatarSpeakFn = (text: string) => void;

export type AvatarSessionControls = {
  sessionState: SessionState;
  isConnected: boolean;
  connectionQuality: ConnectionQuality;
  isAvatarTalking: boolean;
  interrupt: () => void;
  keepAlive: () => void;
  close: () => void;
};

type AvatarPanelProps = {
  sessionToken: string;
  active: boolean;
  onEnded: (reason: 'user' | 'server') => void;
  onSpeakReady?: (speak: AvatarSpeakFn | null) => void;
  onSessionControlsChange?: (controls: AvatarSessionControls | null) => void;
};

export function AvatarPanel({
  sessionToken,
  active,
  onEnded,
  onSpeakReady,
  onSessionControlsChange,
}: AvatarPanelProps) {
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

  const handleClose = useCallback(() => {
    userStoppedRef.current = true;
    void stop();
  }, [stop]);

  const isConnected = sessionState === SessionState.CONNECTED;

  useEffect(() => {
    onSessionControlsChange?.({
      sessionState,
      isConnected,
      connectionQuality,
      isAvatarTalking,
      interrupt: () => void interrupt(),
      keepAlive: () => void keepAlive(),
      close: handleClose,
    });
    return () => onSessionControlsChange?.(null);
  }, [
    connectionQuality,
    handleClose,
    interrupt,
    isAvatarTalking,
    isConnected,
    keepAlive,
    onSessionControlsChange,
    sessionState,
  ]);

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
