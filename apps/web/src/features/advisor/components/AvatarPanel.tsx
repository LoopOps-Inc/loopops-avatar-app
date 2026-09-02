import { useCallback, useEffect, useRef } from 'react';
import type { RefObject } from 'react';
import type { AvatarSessionResponse, UIComponent } from '@loopops/contracts';
import { Mic, MicOff, PhoneOff, Square } from 'lucide-react';
import { CRYSTAL_DARK_CLASS } from '@/components/Crystal';
import { useTranslation } from '@/i18n';
import { useLivekitAvatarSession } from '../hooks/use-livekit-avatar-session';
import { AvatarVideoSurface } from './AvatarVideoSurface';

export type AvatarPanelCommands = {
  setMic: (on: boolean) => void;
};

type AvatarPanelProps = {
  session: AvatarSessionResponse;
  onEnded: (reason: 'user' | 'server') => void;
  onTranscriptFinal: (text: string) => void;
  onCaption: (text: string) => void;
  onUi: (component: UIComponent) => void;
  onActivity: (activity: 'thinking' | 'speaking' | 'idle') => void;
  onTurnComplete: () => void;
  onConnectionError: () => void;
  commandsRef?: RefObject<AvatarPanelCommands | null>;
};

const CONTROL_BUTTON_CLASS = `${CRYSTAL_DARK_CLASS} flex min-h-11 cursor-pointer items-center gap-2 rounded-full px-4 text-xs font-medium text-white/90 transition-colors hover:bg-black/30 disabled:cursor-not-allowed disabled:opacity-40`;

export function AvatarPanel({
  session,
  onEnded,
  onTranscriptFinal,
  onCaption,
  onUi,
  onActivity,
  onTurnComplete,
  onConnectionError,
  commandsRef,
}: AvatarPanelProps) {
  const { t } = useTranslation();
  const videoRef = useRef<HTMLVideoElement>(null);
  const connectionErrorFired = useRef(false);

  const {
    status,
    isConnected,
    micActive,
    micError,
    startMic,
    stopMic,
    sendBargeIn,
  } = useLivekitAvatarSession({
    livekitUrl: session.livekit_url,
    livekitToken: session.livekit_client_token,
    audioWsPath: session.audio_ws_path,
    videoRef,
    handlers: {
      onTranscriptPartial: () => {},
      onTranscriptFinal,
      onThinking: () => onActivity('thinking'),
      onFiller: () => onActivity('thinking'),
      onAgentSpeaking: () => onActivity('speaking'),
      onCaption,
      onUi,
      onTurnComplete,
      onClosed: () => onEnded('server'),
    },
  });

  useEffect(() => {
    if (status === 'failed' && !connectionErrorFired.current) {
      connectionErrorFired.current = true;
      onConnectionError();
    }
  }, [status, onConnectionError]);

  useEffect(() => {
    if (!commandsRef) return;
    commandsRef.current = {
      setMic: (on: boolean) => {
        if (on) {
          void startMic();
        } else {
          stopMic();
        }
      },
    };
    return () => {
      commandsRef.current = null;
    };
  }, [commandsRef, startMic, stopMic]);

  const handleClose = useCallback(() => {
    onEnded('user');
  }, [onEnded]);

  const handleInterrupt = useCallback(() => {
    sendBargeIn();
  }, [sendBargeIn]);

  const toggleMic = useCallback(() => {
    if (micActive) {
      stopMic();
    } else {
      void startMic();
    }
  }, [micActive, startMic, stopMic]);

  return (
    <div className="absolute inset-0 size-full">
      <AvatarVideoSurface videoRef={videoRef} isConnected={isConnected} />

      <div className="pointer-events-none absolute inset-x-0 bottom-4 flex flex-col items-center gap-2 px-4">
        {micError && (
          <p className="text-xs text-white/80">{t('advisor.mic_unavailable')}</p>
        )}
        <div className="pointer-events-auto flex items-center gap-2">
          <button
            type="button"
            onClick={toggleMic}
            disabled={!isConnected}
            aria-pressed={micActive}
            className={CONTROL_BUTTON_CLASS}
          >
            {micActive ? (
              <Mic className="h-4 w-4" aria-hidden="true" />
            ) : (
              <MicOff className="h-4 w-4" aria-hidden="true" />
            )}
            {micActive ? t('advisor.mic_off') : t('advisor.mic_on')}
          </button>
          <button
            type="button"
            onClick={handleInterrupt}
            disabled={!isConnected}
            className={CONTROL_BUTTON_CLASS}
          >
            <Square className="h-3.5 w-3.5" aria-hidden="true" />
            {t('advisor.interrupt')}
          </button>
          <button
            type="button"
            onClick={handleClose}
            aria-label={t('advisor.avatar_hide')}
            title={t('advisor.avatar_hide')}
            className="bg-error hover:bg-error/90 flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-white transition-colors duration-200"
          >
            <PhoneOff className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </div>
  );
}
