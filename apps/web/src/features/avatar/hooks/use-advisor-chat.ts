import { useCallback, useEffect, useRef, useState } from 'react';
import type { UIComponent } from '@loopops/contracts';
import { createMockAdvisorService } from '@/features/advisor/services/mock-advisor-service';
import type { AdvisorService, AdvisorStreamEvent } from '@/features/advisor/services/types';
import { createAdvisorSession } from '@/services/advisor-service';
import type { ChatMessage } from '../types';

type UseAdvisorChatOptions = {
  /** Makes the avatar speak the accumulated speech (session.message). */
  speak: (text: string) => void;
  /** Session connected: gates the greeting turn. */
  enabled: boolean;
  /** Swap point for the real SSE-backed service later. */
  service?: AdvisorService;
  greet?: boolean;
};

type UseAdvisorChatResult = {
  messages: ChatMessage[];
  isThinking: boolean;
  threadStartedAt: string | null;
  send: (message: string) => void;
};

const defaultService = createMockAdvisorService();

function toComponent(event: AdvisorStreamEvent): UIComponent | null {
  if (event.event === 'ui') return event.data;
  if (event.event === 'citations') {
    return { type: 'citations', payload: event.data };
  }
  return null;
}

/**
 * Owns the advisor chat transcript. Streams token events into an avatar
 * bubble, attaches ui cards to it, and on turn completion makes the avatar
 * speak the accumulated speech. HeyGen transcriptions are NOT rendered here
 * (the avatar only speaks what this hook sends, so they would duplicate).
 */
export function useAdvisorChat({
  speak,
  enabled,
  service = defaultService,
  greet = true,
}: UseAdvisorChatOptions): UseAdvisorChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [threadStartedAt, setThreadStartedAt] = useState<string | null>(null);
  const busyRef = useRef(false);
  const greetedRef = useRef(false);
  const disposedRef = useRef(false);
  const messagesRef = useRef(messages);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // StrictMode simulates unmount/remount: re-arm the flag on every real or
  // simulated mount instead of latching disposed forever.
  useEffect(() => {
    disposedRef.current = false;
    return () => {
      disposedRef.current = true;
    };
  }, []);

  const runTurn = useCallback(
    async (stream: AsyncIterable<AdvisorStreamEvent>) => {
      if (busyRef.current || disposedRef.current) return;
      busyRef.current = true;
      setIsThinking(true);
      let speech = '';
      try {
        for await (const event of stream) {
          if (disposedRef.current) return;
          if (event.event === 'token') {
            speech += event.data.text;
            const text = speech;
            setMessages((prev) => {
              const last = prev[prev.length - 1];
              if (last && last.sender === 'avatar') {
                return [...prev.slice(0, -1), { ...last, message: text }];
              }
              return [...prev, { sender: 'avatar', message: text, timestamp: Date.now() }];
            });
          } else {
            const component = toComponent(event);
            if (component) {
              setMessages((prev) => {
                const last = prev[prev.length - 1];
                if (last && last.sender === 'avatar') {
                  const uiComponents = [...(last.uiComponents ?? []), component];
                  return [...prev.slice(0, -1), { ...last, uiComponents }];
                }
                return [
                  ...prev,
                  {
                    sender: 'avatar',
                    message: '',
                    timestamp: Date.now(),
                    uiComponents: [component],
                  },
                ];
              });
            }
          }
        }
        if (!disposedRef.current && speech.trim()) {
          speak(speech.trim());
        }
      } finally {
        busyRef.current = false;
        setIsThinking(false);
      }
    },
    [speak],
  );

  const send = useCallback(
    (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || busyRef.current) return;
      setMessages((prev) => [...prev, { sender: 'user', message: trimmed, timestamp: Date.now() }]);
      void runTurn(service.sendTurn(trimmed));
    },
    [runTurn, service],
  );

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    void createAdvisorSession().then((session) => {
      if (!cancelled) setThreadStartedAt(session.thread_started_at);
    });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !greet || !service.sendGreeting) return;
    // A previous greeting attempt may have been disposed by StrictMode's
    // simulated unmount before producing any message; retry then.
    if (greetedRef.current && messagesRef.current.length > 0) return;
    greetedRef.current = true;
    void runTurn(service.sendGreeting());
  }, [enabled, greet, runTurn, service]);

  return { messages, isThinking, threadStartedAt, send };
}
