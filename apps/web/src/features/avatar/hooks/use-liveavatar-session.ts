import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AgentEventsEnum,
  ConnectionQuality,
  LiveAvatarSession,
  SessionDisconnectReason,
  SessionEvent,
  SessionState,
} from '@heygen/liveavatar-web-sdk';
import { LIVEAVATAR_UI_PREVIEW_TOKEN } from '@/config/avatar';
import type { ChatMessage, MessageSender, SessionEndReason } from '../types';

type UseLiveAvatarSessionOptions = {
  /** Enable mic input (voice mode). The session must be created with it. */
  voiceChat?: boolean;
  /** Skip the SDK: connected UI with no stream (see LIVEAVATAR_UI_PREVIEW_TOKEN). */
  preview?: boolean;
};

type UseLiveAvatarSessionResult = {
  sessionState: SessionState;
  isStreamReady: boolean;
  connectionQuality: ConnectionQuality;
  isUserTalking: boolean;
  isAvatarTalking: boolean;
  isMicMuted: boolean;
  messages: ChatMessage[];
  endReason: SessionEndReason | null;
  isPreview: boolean;
  start: () => Promise<void>;
  stop: () => Promise<void>;
  attach: (element: HTMLMediaElement) => void;
  sendMessage: (message: string) => string;
  /** Lip-sync the given text without invoking the vendor LLM. */
  repeat: (message: string) => string;
  interrupt: () => void;
  keepAlive: () => Promise<void>;
  setMicMuted: (muted: boolean) => void;
};

function mapDisconnectReason(reason: SessionDisconnectReason): SessionEndReason {
  switch (reason) {
    case SessionDisconnectReason.CLIENT_INITIATED:
      return 'user';
    case SessionDisconnectReason.SESSION_START_FAILED:
      return 'error';
    default:
      return 'server';
  }
}

/**
 * React glue over @heygen/liveavatar-web-sdk, adapted from the official demo.
 *
 * The session instance is created once per mount via a lazy useState
 * initializer (StrictMode-safe; creating it in an effect spawns orphaned
 * LiveKit rooms). Consumers remount with a new token for a fresh session.
 * User transcription chunks are cumulative (replace); avatar chunks append.
 *
 * Voice mode: the mic is auto-muted while the avatar speaks (echo guard) and
 * restored afterwards unless the user muted it manually. End reasons come
 * from SESSION_DISCONNECTED; our own stop() wins so UI intents are truthful.
 */
export function useLiveAvatarSession(
  sessionToken: string,
  options: UseLiveAvatarSessionOptions = {},
): UseLiveAvatarSessionResult {
  const voiceChat = options.voiceChat ?? false;
  const preview = options.preview ?? sessionToken === LIVEAVATAR_UI_PREVIEW_TOKEN;

  const startAttemptedRef = useRef(false);
  const userStoppedRef = useRef(false);
  const userMutedRef = useRef(false);

  const [session] = useState(() =>
    preview ? null : new LiveAvatarSession(sessionToken, { voiceChat }),
  );

  const [sessionState, setSessionState] = useState<SessionState>(
    preview ? SessionState.CONNECTED : SessionState.INACTIVE,
  );
  const [connectionQuality, setConnectionQuality] = useState<ConnectionQuality>(
    preview ? ConnectionQuality.GOOD : ConnectionQuality.UNKNOWN,
  );
  const [isStreamReady, setIsStreamReady] = useState(false);
  const [isUserTalking, setIsUserTalking] = useState(false);
  const [isAvatarTalking, setIsAvatarTalking] = useState(false);
  const [isMicMuted, setIsMicMuted] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [endReason, setEndReason] = useState<SessionEndReason | null>(null);
  const currentSenderRef = useRef<MessageSender | null>(null);

  useEffect(() => {
    if (preview || !session) return;

    const handleStateChanged = (state: SessionState) => {
      setSessionState(state);
      if (state === SessionState.DISCONNECTED) {
        setIsStreamReady(false);
      }
    };

    const handleDisconnected = (reason: SessionDisconnectReason) => {
      setEndReason(userStoppedRef.current ? 'user' : mapDisconnectReason(reason));
      session.removeAllListeners();
    };

    const upsertMessage = (sender: MessageSender, text: string, mode: 'replace' | 'append') => {
      currentSenderRef.current = sender;
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last && last.sender === sender) {
          const message = mode === 'replace' ? text : last.message + text;
          return [...prev.slice(0, -1), { ...last, message }];
        }
        return [...prev, { sender, message: text, timestamp: Date.now() }];
      });
    };

    const handleUserChunk = (event: { text: string }) =>
      upsertMessage('user', event.text, 'replace');
    const handleAvatarChunk = (event: { text: string }) =>
      upsertMessage('avatar', event.text, 'append');
    const handleFinal = (event: { text: string }) => {
      currentSenderRef.current = null;
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last) {
          return [...prev.slice(0, -1), { ...last, message: event.text }];
        }
        return prev;
      });
    };

    session.on(SessionEvent.SESSION_STATE_CHANGED, handleStateChanged);
    session.on(SessionEvent.SESSION_DISCONNECTED, handleDisconnected);
    session.on(SessionEvent.SESSION_STREAM_READY, () => setIsStreamReady(true));
    session.on(SessionEvent.SESSION_CONNECTION_QUALITY_CHANGED, setConnectionQuality);

    session.on(AgentEventsEnum.USER_SPEAK_STARTED, () => setIsUserTalking(true));
    session.on(AgentEventsEnum.USER_SPEAK_ENDED, () => setIsUserTalking(false));
    session.on(AgentEventsEnum.AVATAR_SPEAK_STARTED, () => setIsAvatarTalking(true));
    session.on(AgentEventsEnum.AVATAR_SPEAK_ENDED, () => setIsAvatarTalking(false));

    session.on(AgentEventsEnum.USER_TRANSCRIPTION_CHUNK, handleUserChunk);
    session.on(AgentEventsEnum.AVATAR_TRANSCRIPTION_CHUNK, handleAvatarChunk);
    session.on(AgentEventsEnum.USER_TRANSCRIPTION, handleFinal);
    session.on(AgentEventsEnum.AVATAR_TRANSCRIPTION, handleFinal);

    return () => {
      session.removeAllListeners();
    };
  }, [preview, session]);

  // Echo guard: mute the mic while the avatar speaks, restore afterwards
  // unless the user muted it manually. Only for voice sessions.
  useEffect(() => {
    if (preview || !session || !voiceChat || !isAvatarTalking) return;
    void session.voiceChat
      .mute()
      .then(() => setIsMicMuted(true))
      .catch(() => {});
    return () => {
      if (!userMutedRef.current) {
        void session.voiceChat
          .unmute()
          .then(() => setIsMicMuted(false))
          .catch(() => {});
      }
    };
  }, [isAvatarTalking, preview, session, voiceChat]);

  // Keep idle-but-active sessions alive while the page is visible.
  useEffect(() => {
    if (preview || !session || sessionState !== SessionState.CONNECTED) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void session.keepAlive().catch(() => {});
      }
    }, 25_000);
    return () => window.clearInterval(id);
  }, [preview, session, sessionState]);

  const start = useCallback(async () => {
    if (preview || !session) return;
    if (startAttemptedRef.current) return;
    startAttemptedRef.current = true;
    try {
      await session.start();
    } catch (err) {
      startAttemptedRef.current = false;
      throw err;
    }
  }, [preview, session]);

  const stop = useCallback(async () => {
    userStoppedRef.current = true;
    setEndReason('user');
    if (preview || !session) return;
    await session.stop();
  }, [preview, session]);

  const attach = useCallback(
    (element: HTMLMediaElement) => {
      if (preview || !session) return;
      session.attach(element);
    },
    [preview, session],
  );

  const sendMessage = useCallback(
    (message: string) => {
      if (preview || !session) return '';
      return session.message(message);
    },
    [preview, session],
  );

  const repeat = useCallback(
    (message: string) => {
      if (preview || !session) return '';
      return session.repeat(message);
    },
    [preview, session],
  );

  const interrupt = useCallback(() => {
    if (preview || !session) return;
    return session.interrupt();
  }, [preview, session]);

  const keepAlive = useCallback(async () => {
    if (preview || !session) return;
    return session.keepAlive();
  }, [preview, session]);

  const setMicMuted = useCallback(
    (muted: boolean) => {
      userMutedRef.current = muted;
      if (preview || !session) {
        setIsMicMuted(muted);
        return;
      }
      const action = muted ? session.voiceChat.mute : session.voiceChat.unmute;
      void action
        .call(session.voiceChat)
        .then(() => setIsMicMuted(muted))
        .catch(() => setIsMicMuted(session.voiceChat.isMuted));
    },
    [preview, session],
  );

  return {
    sessionState,
    isStreamReady,
    connectionQuality,
    isUserTalking,
    isAvatarTalking,
    isMicMuted,
    messages,
    endReason,
    isPreview: preview,
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
