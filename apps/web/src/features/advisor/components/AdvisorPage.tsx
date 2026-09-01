import { useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Loader2, Send, Sparkles } from 'lucide-react';
import { AppShell } from '@/components/AppShell';
import { appEnv } from '@/config/env';
import { useTranslation } from '@/i18n';
import { useAdvisorChat } from '../hooks/use-advisor-chat';
import { UIPayloadRenderer } from './UIPayloadRenderer';

const SUGGESTIONS = ['advisor.suggestion_portfolio', 'advisor.suggestion_market'] as const;

function MessageBubble({
  role,
  text,
  streaming,
  chips,
  onChipClick,
  children,
}: {
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
  chips?: { id: string; label: string }[];
  onChipClick?: (label: string) => void;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  const isUser = role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[min(100%,36rem)] rounded-xs border px-4 py-3 ${
          isUser ? 'border-accent/20 bg-accent/10' : 'border-outline bg-surface'
        }`}
      >
        <p className="text-content-muted mb-1 text-[11px] font-medium tracking-wide uppercase">
          {isUser ? t('advisor.you') : t('advisor.assistant')}
        </p>
        {text && (
          <p className="text-sm leading-relaxed">
            {text}
            {streaming && (
              <span className="bg-content-sub ml-0.5 inline-block h-4 w-0.5 animate-pulse motion-reduce:animate-none" />
            )}
          </p>
        )}
        {children && <div className="mt-3">{children}</div>}
        {chips && chips.length > 0 && !streaming && (
          <div className="mt-3 flex flex-wrap gap-2">
            {chips.map((chip) => (
              <button
                key={chip.id}
                type="button"
                onClick={() => onChipClick?.(chip.label)}
                className="border-outline text-content hover:bg-surface-sub cursor-pointer rounded-full border px-3 py-1.5 text-xs transition-colors"
              >
                {chip.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export function AdvisorRoute() {
  const { t } = useTranslation();
  const { session, messages, phase, error, sendMessage, isReady, isThinking } = useAdvisorChat();
  const [input, setInput] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || !isReady || isThinking) return;
    void sendMessage(trimmed);
    setInput('');
  };

  const handleSuggestion = (key: (typeof SUGGESTIONS)[number]) => {
    if (!isReady || isThinking) return;
    void sendMessage(t(key));
  };

  const loading = phase === 'loading_session';

  return (
    <AppShell>
      <div className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-4 sm:p-6">
        <header className="border-outline flex flex-col gap-1 border-b pb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="text-content-sub h-5 w-5" aria-hidden="true" />
            <h1 className="font-heading text-xl font-semibold">{t('advisor.title')}</h1>
          </div>
          <p className="text-content-sub text-sm">{t('advisor.subtitle')}</p>
          {session && (
            <p className="text-content-muted text-xs">
              {t('advisor.greeting', { name: session.client.first_name })}
            </p>
          )}
          {appEnv.advisorMock && (
            <p className="text-content-muted text-xs">{t('advisor.mock_notice')}</p>
          )}
        </header>

        <div
          role="log"
          aria-live="polite"
          className="flex min-h-64 flex-1 flex-col gap-4 overflow-y-auto"
        >
          {loading && (
            <div className="text-content-muted flex flex-1 items-center justify-center gap-2 text-sm">
              <Loader2
                className="h-5 w-5 animate-spin motion-reduce:animate-none"
                aria-hidden="true"
              />
              {t('advisor.loading')}
            </div>
          )}

          {!loading && messages.length === 0 && (
            <div className="flex flex-col gap-3 py-8">
              <p className="text-content-sub text-center text-sm">{t('advisor.empty')}</p>
              <div className="flex flex-wrap justify-center gap-2">
                {SUGGESTIONS.map((key) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => handleSuggestion(key)}
                    disabled={!isReady || isThinking}
                    className="border-outline text-content hover:bg-surface-sub cursor-pointer rounded-full border px-4 py-2 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {t(key)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((message) => (
            <MessageBubble
              key={message.id}
              role={message.role}
              text={message.text}
              streaming={message.streaming}
              chips={message.chips}
              onChipClick={(label) => void sendMessage(label)}
            >
              {message.uiPayload.length > 0 && <UIPayloadRenderer components={message.uiPayload} />}
            </MessageBubble>
          ))}
          <div ref={endRef} />
        </div>

        {error && (
          <div
            role="alert"
            className="border-error/30 bg-error/10 text-error rounded-xs border px-4 py-3 text-sm"
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="border-outline flex gap-2 border-t pt-4">
          <label htmlFor="advisor-input" className="sr-only">
            {t('advisor.input_label')}
          </label>
          <input
            id="advisor-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={t('advisor.input_placeholder')}
            disabled={!isReady || isThinking}
            autoComplete="off"
            className="border-outline bg-surface text-content placeholder:text-content-muted focus:border-content-sub min-h-11 flex-1 rounded-xs border px-4 text-sm transition-colors focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!isReady || isThinking || !input.trim()}
            className="rounded-cta bg-filled-dark text-filled-dark-fg flex min-h-11 cursor-pointer items-center gap-2 px-5 text-sm font-medium transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
          >
            {isThinking ? (
              <Loader2
                className="h-4 w-4 animate-spin motion-reduce:animate-none"
                aria-hidden="true"
              />
            ) : (
              <Send className="h-4 w-4" aria-hidden="true" />
            )}
            {t('advisor.send')}
          </button>
        </form>

        <p className="text-content-muted text-center text-xs">
          <a href="/demo" className="text-accent hover:underline">
            {t('advisor.link_demo')}
          </a>
        </p>
      </div>
    </AppShell>
  );
}
