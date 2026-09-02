import { useCallback, useEffect, useRef, useState } from 'react';
import type { UIComponent } from '@loopops/contracts';
import { t } from '@/i18n';
import type { AdvisorService, AdvisorStreamEvent } from '../services/types';
import type { ChatMessage } from '../types';

type UseAdvisorChatOptions = {
  speak: (text: string) => void;
  enabled: boolean;
  service?: AdvisorService;
  greet?: boolean;
};

type UseAdvisorChatResult = {
  messages: ChatMessage[];
  isThinking: boolean;
  send: (message: string) => void;
  appendUserMessage: (text: string) => void;
  appendCaption: (text: string) => void;
  appendUi: (component: UIComponent) => void;
  endVoiceTurn: () => void;
};

function toComponent(event: AdvisorStreamEvent): UIComponent | null {
  if (event.event === 'ui') return event.data;
  if (event.event === 'citations') {
    return { type: 'citations', payload: event.data };
  }
  return null;
}

export function useAdvisorChat({
  speak,
  enabled,
  service,
  greet = true,
}: UseAdvisorChatOptions): UseAdvisorChatResult {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const busyRef = useRef(false);
  const greetedRef = useRef(false);
  const disposedRef = useRef(false);
  const voiceOpenRef = useRef(false);
  const messagesRef = useRef(messages);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  useEffect(() => {
    disposedRef.current = false;
    return () => {
      disposedRef.current = true;
    };
  }, []);

  const appendAvatarMessage = useCallback((message: string) => {
    setMessages((prev) => [...prev, { sender: 'avatar', message, timestamp: Date.now() }]);
  }, []);

  const runTurn = useCallback(
    async (stream: AsyncIterable<AdvisorStreamEvent>) => {
      if (busyRef.current || disposedRef.current) return;
      busyRef.current = true;
      setIsThinking(true);
      voiceOpenRef.current = false;
      let speech = '';
      let errorSpeech = '';
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
          } else if (event.event === 'error') {
            const text =
              event.data.message || t('advisor.error_event', { code: event.data.code });
            appendAvatarMessage(text);
            if (event.data.message && !speech.trim()) {
              errorSpeech = event.data.message;
            }
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
        const toSpeak = speech.trim() || errorSpeech.trim();
        if (!disposedRef.current && toSpeak) {
          speak(toSpeak);
        }
      } catch (err) {
        if (!disposedRef.current) {
          appendAvatarMessage(
            err instanceof Error && err.message ? err.message : t('live.error_unknown'),
          );
        }
      } finally {
        busyRef.current = false;
        setIsThinking(false);
      }
    },
    [appendAvatarMessage, speak],
  );

  const send = useCallback(
    (message: string) => {
      const trimmed = message.trim();
      if (!trimmed || busyRef.current || !service) return;
      voiceOpenRef.current = false;
      setMessages((prev) => [...prev, { sender: 'user', message: trimmed, timestamp: Date.now() }]);
      void runTurn(service.sendTurn(trimmed));
    },
    [runTurn, service],
  );

  useEffect(() => {
    if (!enabled || !greet || !service?.sendGreeting) return;
    if (greetedRef.current && messagesRef.current.length > 0) return;
    greetedRef.current = true;
    void runTurn(service.sendGreeting());
  }, [enabled, greet, runTurn, service]);

  const appendUserMessage = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    setMessages((prev) => [...prev, { sender: 'user', message: trimmed, timestamp: Date.now() }]);
  }, []);

  const appendCaption = useCallback((text: string) => {
    if (!text) return;
    const continuesOpenTurn = voiceOpenRef.current;
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (continuesOpenTurn && last && last.sender === 'avatar') {
        return [...prev.slice(0, -1), { ...last, message: text }];
      }
      return [...prev, { sender: 'avatar', message: text, timestamp: Date.now() }];
    });
    voiceOpenRef.current = true;
  }, []);

  const appendUi = useCallback((component: UIComponent) => {
    const continuesOpenTurn = voiceOpenRef.current;
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (continuesOpenTurn && last && last.sender === 'avatar') {
        const uiComponents = [...(last.uiComponents ?? []), component];
        return [...prev.slice(0, -1), { ...last, uiComponents }];
      }
      return [
        ...prev,
        { sender: 'avatar', message: '', timestamp: Date.now(), uiComponents: [component] },
      ];
    });
    voiceOpenRef.current = true;
  }, []);

  const endVoiceTurn = useCallback(() => {
    voiceOpenRef.current = false;
  }, []);

  return {
    messages,
    isThinking,
    send,
    appendUserMessage,
    appendCaption,
    appendUi,
    endVoiceTurn,
  };
}
