import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AgentEventsEnum,
  ConnectionQuality,
  LiveAvatarSession,
  SessionDisconnectReason,
  SessionEvent,
  SessionState,
} from '@heygen/liveavatar-web-sdk';
import type { ChatMessage, MessageSender, SessionEndReason } from '../types';

type UseLiveAvatarSessionOptions = {
  /** Enable mic input (voice mode). The session must be created with it. */
  voiceChat?: boolean;
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

  const startAttemptedRef = useRef(false);
  const userStoppedRef = useRef(false);
  const userMutedRef = useRef(false);

  const [session] = useState(() => new LiveAvatarSession(sessionToken, { voiceChat }));

  const [sessionState, setSessionState] = useState<SessionState>(SessionState.INACTIVE);
  const [connectionQuality, setConnectionQuality] = useState<ConnectionQuality>(
    ConnectionQuality.UNKNOWN,
  );
  const [isStreamReady, setIsStreamReady] = useState(false);
  const [isUserTalking, setIsUserTalking] = useState(false);
  const [isAvatarTalking, setIsAvatarTalking] = useState(false);
  const [isMicMuted, setIsMicMuted] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [endReason, setEndReason] = useState<SessionEndReason | null>(null);
  const currentSenderRef = useRef<MessageSender | null>(null);

  useEffect(() => {
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
  }, [session]);

  // Echo guard: mute the mic while the avatar speaks, restore afterwards
  // unless the user muted it manually. Only for voice sessions.
  useEffect(() => {
    if (!voiceChat || !isAvatarTalking) return;
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
  }, [isAvatarTalking, session, voiceChat]);

  // Keep idle-but-active sessions alive while the page is visible.
  useEffect(() => {
    if (sessionState !== SessionState.CONNECTED) return;
    const id = window.setInterval(() => {
      if (document.visibilityState === 'visible') {
        void session.keepAlive().catch(() => {});
      }
    }, 25_000);
    return () => window.clearInterval(id);
  }, [sessionState, session]);

  const start = useCallback(async () => {
    if (startAttemptedRef.current) return;
    startAttemptedRef.current = true;
    try {
      await session.start();
    } catch (err) {
      startAttemptedRef.current = false;
      throw err;
    }
  }, [session]);

  const stop = useCallback(async () => {
    userStoppedRef.current = true;
    setEndReason('user');
    await session.stop();
  }, [session]);

  const attach = useCallback(
    (element: HTMLMediaElement) => {
      session.attach(element);
    },
    [session],
  );

  const sendMessage = useCallback(
    (message: string) => {
      return session.message(message);
    },
    [session],
  );

  const repeat = useCallback(
    (message: string) => {
      return session.repeat(message);
    },
    [session],
  );

  const interrupt = useCallback(() => {
    return session.interrupt();
  }, [session]);

  const keepAlive = useCallback(async () => {
    return session.keepAlive();
  }, [session]);

  const setMicMuted = useCallback(
    (muted: boolean) => {
      userMutedRef.current = muted;
      const action = muted ? session.voiceChat.mute : session.voiceChat.unmute;
      void action
        .call(session.voiceChat)
        .then(() => setIsMicMuted(muted))
        .catch(() => setIsMicMuted(session.voiceChat.isMuted));
    },
    [session],
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
