import { useCallback, useEffect, useRef, useState } from 'react';
import type { SseErrorEvent, SessionResponse, UIComponent } from '@loopops/contracts';
import {
  ackFirstTurnDisclosures,
  createAdvisorSession,
  sendAdvisorMessage,
} from '@/services/advisor-service';
import { getLocale, t } from '@/i18n';
import type { AdvisorMessage, AdvisorPhase, VoiceActivity } from '../types';

function newId(): string {
  return crypto.randomUUID();
}

export function useAdvisorChat() {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [messages, setMessages] = useState<AdvisorMessage[]>([]);
  const [phase, setPhase] = useState<AdvisorPhase>('loading_session');
  const [error, setError] = useState<string | null>(null);
  const [voiceActivity, setVoiceActivity] = useState<VoiceActivity>('idle');
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const next = await createAdvisorSession();
        await ackFirstTurnDisclosures();
        if (!cancelled) {
          setSession(next);
          setPhase('ready');
          setMessages([
            {
              id: newId(),
              role: 'assistant',
              text: t('advisor.greeting', { name: next.client.first_name }),
              uiPayload: [],
              timestamp: Date.now(),
            },
          ]);
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
      abortRef.current?.abort();
    };
  }, []);

  const appendUserMessage = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((prev) => [
      ...prev,
      {
        id: newId(),
        role: 'user',
        text: trimmed,
        uiPayload: [],
        timestamp: Date.now(),
      },
    ]);
  }, []);

  const beginAssistantTurn = useCallback(() => {
    const id = newId();
    setMessages((prev) => [
      ...prev,
      {
        id,
        role: 'assistant',
        text: '',
        uiPayload: [],
        timestamp: Date.now(),
        streaming: true,
      },
    ]);
    return id;
  }, []);

  const setAssistantText = useCallback((id: string, text: string) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, text } : m)));
  }, []);

  const appendAssistantUi = useCallback((id: string, component: UIComponent) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, uiPayload: [...m.uiPayload, component] } : m)),
    );
  }, []);

  const endAssistantTurn = useCallback((id: string) => {
    setMessages((prev) => prev.map((m) => (m.id === id ? { ...m, streaming: false } : m)));
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!session || phase === 'thinking') return;

      const trimmed = text.trim();
      if (!trimmed) return;

      appendUserMessage(trimmed);

      const assistantId = newId();
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: 'assistant',
          text: '',
          uiPayload: [],
          timestamp: Date.now(),
          streaming: true,
        },
      ]);
      setPhase('thinking');
      setError(null);

      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      const handleSseError = (sseError: SseErrorEvent) => {
        setError(t('advisor.error_event', { code: sseError.code }));
      };

      try {
        await sendAdvisorMessage(
          session.thread_id,
          {
            text: trimmed,
            locale: getLocale(),
            client_turn_id: newId(),
          },
          {
            onToken: (chunk) => {
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, text: m.text + chunk } : m)),
              );
            },
            onUi: (component) => {
              appendAssistantUi(assistantId, component);
            },
            onCitations: (citations) => {
              appendAssistantUi(assistantId, {
                type: 'citations',
                payload: { items: citations.items },
              });
            },
            onFormSpec: () => {},
            onError: handleSseError,
            onDone: () => {
              setMessages((prev) =>
                prev.map((m) => (m.id === assistantId ? { ...m, streaming: false } : m)),
              );
            },
          },
          controller.signal,
        );
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : t('advisor.error_unknown'));
        setMessages((prev) => prev.filter((m) => m.id !== assistantId));
      } finally {
        setPhase('ready');
      }
    },
    [session, phase, appendUserMessage, appendAssistantUi],
  );

  return {
    session,
    messages,
    phase,
    error,
    voiceActivity,
    setVoiceActivity,
    sendMessage,
    appendUserMessage,
    beginAssistantTurn,
    setAssistantText,
    appendAssistantUi,
    endAssistantTurn,
    isReady: phase === 'ready' || phase === 'thinking',
    isThinking: phase === 'thinking',
  };
}
