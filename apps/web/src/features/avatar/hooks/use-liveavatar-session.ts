import { useCallback, useRef, useState } from 'react';
import type { RefObject } from 'react';
import type { AvatarSessionResponse, UIComponent } from '@loopops/contracts';
import { useLivekitAvatarSession } from '@/features/advisor/hooks/use-livekit-avatar-session';
import { stopAvatarSession } from '@/services/advisor-service';
import type { ConnectionQuality, SessionState } from '../lib/session-status';
import type { SessionEndReason } from '../types';

type UseLiveAvatarSessionOptions = {
  voiceChat?: boolean;
  audioUnlockedRef?: RefObject<boolean>;
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
  videoRef: React.RefObject<HTMLVideoElement>;
  start: () => Promise<void>;
  stop: () => Promise<void>;
  attach: (element: HTMLMediaElement) => void;
  sendMessage: (message: string) => string;
  speak: (text: string) => void;
  repeat: (message: string) => void;
  interrupt: () => void;
  keepAlive: () => Promise<void>;
  setMicMuted: (muted: boolean) => void;
  unlockPlayback: (unmute?: boolean) => Promise<boolean>;
};

const LIVEKIT_QUALITY_MAP: Record<string, ConnectionQuality> = {
  good: 'GOOD',
  poor: 'BAD',
  lost: 'BAD',
};

export function useLiveAvatarSession(
  avatarSession: AvatarSessionResponse,
  { audioUnlockedRef, onTranscriptFinal, onCaption, onUi }: UseLiveAvatarSessionOptions = {},
): UseLiveAvatarSessionResult {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const videoElementRef = videoRef as React.RefObject<HTMLVideoElement>;
  const userStoppedRef = useRef(false);
  const [isAvatarTalking, setIsAvatarTalking] = useState(false);
  const [endedFor, setEndedFor] = useState<{ sessionId: string; reason: SessionEndReason } | null>(
    null,
  );
  const sessionId = avatarSession.avatar_session_id;
  const endReason = endedFor?.sessionId === sessionId ? endedFor.reason : null;

  const livekit = useLivekitAvatarSession({
    livekitUrl: avatarSession.livekit_url,
    livekitToken: avatarSession.livekit_client_token,
    audioWsPath: avatarSession.audio_ws_path,
    videoRef: videoElementRef,
    audioUnlockedRef,
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
        if (!userStoppedRef.current) setEndedFor({ sessionId, reason: 'server' });
      },
    },
  });
  const { sendBargeIn, sendKeepAlive, sendSpeak, startMic, stopMic, unlockPlayback } = livekit;

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
    setEndedFor({ sessionId, reason: 'user' });
    void stopAvatarSession(avatarSession.avatar_session_id, 'user').catch(() => {});
  }, [avatarSession.avatar_session_id, sessionId]);

  const attach = useCallback((element: HTMLMediaElement) => {
    videoRef.current = element as HTMLVideoElement;
  }, []);

  const sendMessage = useCallback(() => '', []);

  const speak = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (trimmed) sendSpeak(trimmed);
    },
    [sendSpeak],
  );

  const repeat = useCallback(
    (message: string) => {
      speak(message);
    },
    [speak],
  );

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
    videoRef: videoElementRef,
    start,
    stop,
    attach,
    sendMessage,
    speak,
    repeat,
    interrupt,
    keepAlive,
    setMicMuted,
    unlockPlayback,
  };
}
