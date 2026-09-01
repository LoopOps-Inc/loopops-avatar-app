import { useCallback, useEffect, useRef, useState } from 'react';
import type { SessionResponse, UIComponent } from '@loopops/contracts';
import { createAdvisorSession, sendAdvisorMessage } from '@/services/advisor-service';
import { appEnv } from '@/config/env';
import { t } from '@/i18n';
import { sendMockAdvisorMessage } from '@/services/advisor-mock';
import type { AdvisorMessage, AdvisorPhase } from '../types';

function newId(): string {
  return crypto.randomUUID();
}

type UseAdvisorChatOptions = {
  /** Called with the assistant narrative when a turn finishes (for avatar lip-sync). */
  onAssistantSpeech?: (text: string) => void;
};

export function useAdvisorChat(options: UseAdvisorChatOptions = {}) {
  const { onAssistantSpeech } = options;
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [messages, setMessages] = useState<AdvisorMessage[]>([]);
  const [phase, setPhase] = useState<AdvisorPhase>('loading_session');
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await createAdvisorSession();
        if (!cancelled) {
          setSession(next);
          setPhase('ready');
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : t('advisor.error_unknown'));
          setPhase('error');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!session || phase === 'thinking') return;

      const trimmed = text.trim();
      if (!trimmed) return;

      const userMessage: AdvisorMessage = {
        id: newId(),
        role: 'user',
        text: trimmed,
        uiPayload: [],
        timestamp: Date.now(),
      };

      const assistantId = newId();
      const assistantMessage: AdvisorMessage = {
        id: assistantId,
        role: 'assistant',
        text: '',
        uiPayload: [],
        timestamp: Date.now(),
        streaming: true,
      };

      setMessages((prev) => [...prev, userMessage, assistantMessage]);
      setPhase('thinking');
      setError(null);

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      let assistantSpeech = '';

      try {
        const runMock = appEnv.advisorMock;
        const handlers = {
          onToken: (chunk: string) => {
            assistantSpeech += chunk;
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + chunk } : m)),
            );
          },
          onUi: (component: UIComponent) => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, uiPayload: [...m.uiPayload, component] } : m,
              ),
            );
          },
          onError: (sseError: { message: string }) => {
            setError(sseError.message);
          },
          onDone: () => {
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)),
            );
            setPhase('ready');
            const speech = assistantSpeech.trim();
            if (speech) {
              onAssistantSpeech?.(speech);
            }
          },
        };

        if (runMock) {
          const meta = await sendMockAdvisorMessage(trimmed, handlers);
          if (meta.chips?.length) {
            setMessages((prev) =>
              prev.map((m) => (m.id === assistantId ? { ...m, chips: meta.chips } : m)),
            );
          }
        } else {
          await sendAdvisorMessage(
            session.thread_id,
            { message: trimmed },
            handlers,
            controller.signal,
          );
        }
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : t('advisor.error_unknown'));
        setPhase('error');
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      }
    },
    [session, phase, onAssistantSpeech],
  );

  return {
    session,
    messages,
    phase,
    error,
    sendMessage,
    isReady: phase === 'ready' || phase === 'thinking',
    isThinking: phase === 'thinking',
  };
}
