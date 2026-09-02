import { useCallback, useRef, useState } from 'react';
import type { UIComponent } from '@loopops/contracts';
import type { AvatarSessionResponse } from '@loopops/contracts';
import { useLivekitAvatarSession } from '@/features/advisor/hooks/use-livekit-avatar-session';
import { stopAvatarSession } from '@/services/advisor-service';
import type { ConnectionQuality, SessionState } from '../lib/session-status';
import type { SessionEndReason } from '../types';

type UseLiveAvatarSessionOptions = {
  voiceChat?: boolean;
  onTranscriptFinal?: (text: string) => void;
  onCaption?: (text: string) => void;
  onUi?: (component: UIComponent) => void;
};

type UseLiveAvatarSessionResult = {
  sessionState: SessionState;
  isStreamReady: boolean;
  connectionQuality: ConnectionQuality;
  isUserTalking: boolean;
  isAvatarTalking: boolean;
  isMicMuted: boolean;
  micError: boolean;
  endReason: SessionEndReason | null;
  videoRef: React.RefObject<HTMLVideoElement | null>;
  start: () => Promise<void>;
  stop: () => Promise<void>;
  attach: (element: HTMLMediaElement) => void;
  sendMessage: (message: string) => string;
  repeat: (message: string) => void;
  interrupt: () => void;
  keepAlive: () => Promise<void>;
  setMicMuted: (muted: boolean) => void;
};

const LIVEKIT_QUALITY_MAP: Record<string, ConnectionQuality> = {
  good: 'GOOD',
  poor: 'BAD',
  lost: 'BAD',
};

export function useLiveAvatarSession(
  avatarSession: AvatarSessionResponse,
  { onTranscriptFinal, onCaption, onUi }: UseLiveAvatarSessionOptions = {},
): UseLiveAvatarSessionResult {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const userStoppedRef = useRef(false);
  const [isAvatarTalking, setIsAvatarTalking] = useState(false);
  const [endReason, setEndReason] = useState<SessionEndReason | null>(null);

  const livekit = useLivekitAvatarSession({
    livekitUrl: avatarSession.livekit_url,
    livekitToken: avatarSession.livekit_client_token,
    audioWsPath: avatarSession.audio_ws_path,
    videoRef,
    handlers: {
      onTranscriptPartial: () => {},
      onTranscriptFinal: (text) => onTranscriptFinal?.(text),
      onThinking: () => setIsAvatarTalking(false),
      onFiller: () => {},
      onAgentSpeaking: () => setIsAvatarTalking(true),
      onCaption: (text) => {
        setIsAvatarTalking(true);
        onCaption?.(text);
      },
      onUi: (component) => onUi?.(component),
      onTurnComplete: () => setIsAvatarTalking(false),
      onClosed: () => {
        if (!userStoppedRef.current) setEndReason('server');
      },
    },
  });
  const { sendBargeIn, sendKeepAlive, startMic, stopMic } = livekit;

  const resolvedEndReason: SessionEndReason | null =
    endReason ?? (livekit.status === 'failed' ? 'error' : null);

  const sessionState: SessionState =
    livekit.status === 'connected'
      ? 'CONNECTED'
      : livekit.status === 'connecting' || livekit.status === 'reconnecting'
        ? 'CONNECTING'
        : 'DISCONNECTED';

  const connectionQuality: ConnectionQuality =
    LIVEKIT_QUALITY_MAP[livekit.connectionQuality] ?? 'UNKNOWN';

  const start = useCallback(async () => {}, []);

  const stop = useCallback(async () => {
    userStoppedRef.current = true;
    setEndReason('user');
    void stopAvatarSession(avatarSession.avatar_session_id, 'user').catch(() => {});
  }, [avatarSession.avatar_session_id]);

  const attach = useCallback((element: HTMLMediaElement) => {
    videoRef.current = element as HTMLVideoElement;
  }, []);

  const sendMessage = useCallback(() => '', []);

  const repeat = useCallback(() => {}, []);

  const interrupt = useCallback(() => {
    sendBargeIn();
  }, [sendBargeIn]);

  const keepAlive = useCallback(async () => {
    sendKeepAlive();
  }, [sendKeepAlive]);

  const setMicMuted = useCallback(
    (muted: boolean) => {
      if (muted) {
        stopMic();
      } else {
        void startMic();
      }
    },
    [startMic, stopMic],
  );

  return {
    sessionState,
    isStreamReady: livekit.isConnected,
    connectionQuality,
    isUserTalking: livekit.micActive,
    isAvatarTalking,
    isMicMuted: !livekit.micActive,
    micError: livekit.micError,
    endReason: resolvedEndReason,
    videoRef,
    start,
    stop,
    attach,
    sendMessage,
    repeat,
    interrupt,
    keepAlive,
    setMicMuted,
  };
}
