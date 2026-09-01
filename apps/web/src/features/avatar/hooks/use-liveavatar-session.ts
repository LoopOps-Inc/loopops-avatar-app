import { useCallback, useEffect, useRef, useState } from 'react';
import {
  AgentEventsEnum,
  ConnectionQuality,
  LiveAvatarSession,
  SessionEvent,
  SessionState,
} from '@heygen/liveavatar-web-sdk';
import type { ChatMessage, MessageSender } from '../types';

type UseLiveAvatarSessionResult = {
  sessionState: SessionState;
  isStreamReady: boolean;
  connectionQuality: ConnectionQuality;
  isUserTalking: boolean;
  isAvatarTalking: boolean;
  messages: ChatMessage[];
  start: () => Promise<void>;
  stop: () => Promise<void>;
  attach: (element: HTMLMediaElement) => void;
  sendMessage: (message: string) => Promise<unknown>;
  /** Lip-sync the given text without invoking the vendor LLM. */
  repeat: (message: string) => string;
  interrupt: () => unknown;
  keepAlive: () => Promise<unknown>;
};

/**
 * React glue over @heygen/liveavatar-web-sdk, adapted from the official demo.
 *
 * The session instance is created once per mount via a lazy useState
 * initializer. Creating it inside an effect under React StrictMode spawns two
 * sessions — the first one orphaned but still running server-side, which
 * wastes a session slot and shows up as two LiveKit rooms. Consumers must
 * remount with a new token for a fresh session; the demo page does exactly
 * that. User transcription chunks are cumulative (full phrase so far, replace
 * the last user message); avatar chunks are individual words (append).
 */
export function useLiveAvatarSession(sessionToken: string): UseLiveAvatarSessionResult {
  const startAttemptedRef = useRef(false);

  const [session] = useState(() => new LiveAvatarSession(sessionToken, { voiceChat: false }));

  const [sessionState, setSessionState] = useState<SessionState>(SessionState.INACTIVE);
  const [connectionQuality, setConnectionQuality] = useState<ConnectionQuality>(
    ConnectionQuality.UNKNOWN,
  );
  const [isStreamReady, setIsStreamReady] = useState(false);
  const [isUserTalking, setIsUserTalking] = useState(false);
  const [isAvatarTalking, setIsAvatarTalking] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const currentSenderRef = useRef<MessageSender | null>(null);

  useEffect(() => {
    const handleStateChanged = (state: SessionState) => {
      setSessionState(state);
      if (state === SessionState.DISCONNECTED) {
        session.removeAllListeners();
        setIsStreamReady(false);
      }
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
    await session.stop();
  }, [session]);

  const attach = useCallback(
    (element: HTMLMediaElement) => {
      session.attach(element);
    },
    [session],
  );

  const sendMessage = useCallback(
    async (message: string) => {
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

  return {
    sessionState,
    isStreamReady,
    connectionQuality,
    isUserTalking,
    isAvatarTalking,
    messages,
    start,
    stop,
    attach,
    sendMessage,
    repeat,
    interrupt,
    keepAlive,
  };
}
