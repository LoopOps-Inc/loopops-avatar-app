import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Loader2, Send, Sparkles, X } from 'lucide-react';
import { AppShell } from '@/components/AppShell';
import { CRYSTAL_DARK_CLASS, CRYSTAL_DARK_STRONG_CLASS } from '@/components/Crystal';
import { appEnv } from '@/config/env';
import { useEmbeddedMode } from '@/hooks/use-embedded-mode';
import { useTranslation } from '@/i18n';
import { useAdvisorAvatar } from '../hooks/use-advisor-avatar';
import { useAdvisorChat } from '../hooks/use-advisor-chat';
import { AvatarPanel, type AvatarSpeakFn } from './AvatarPanel';
import { ChatVideoSwitch } from './ChatVideoSwitch';
import { UIPayloadRenderer } from './UIPayloadRenderer';

const SUGGESTIONS = ['advisor.suggestion_portfolio', 'advisor.suggestion_market'] as const;

function MessageBubble({
  role,
  text,
  streaming,
  chips,
  onChipClick,
  overlay = false,
  children,
}: {
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
  chips?: { id: string; label: string }[];
  onChipClick?: (label: string) => void;
  overlay?: boolean;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  const isUser = role === 'user';

  if (overlay) {
    return (
      <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
        <div
          className={`${CRYSTAL_DARK_CLASS} max-w-[min(100%,36rem)] rounded-2xl px-4 py-3 text-white`}
        >
          {text && (
            <p className="text-sm leading-relaxed text-white/90">
              {text}
              {streaming && (
                <span className="ml-0.5 inline-block h-4 w-0.5 animate-pulse bg-white/60 motion-reduce:animate-none" />
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
                  className={`${CRYSTAL_DARK_CLASS} cursor-pointer rounded-full border border-white/20 px-3 py-1.5 text-xs text-white/90 transition-colors hover:bg-black/30`}
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

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[min(100%,36rem)] rounded-sm px-4 py-3 ${
          isUser ? 'bg-filled-dark text-filled-dark-fg' : 'border-outline bg-surface-sub border'
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
                className="border-outline bg-surface-sub text-content hover:bg-surface cursor-pointer rounded-full border px-3 py-1.5 text-xs transition-colors"
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
  const embedded = useEmbeddedMode();
  const avatar = useAdvisorAvatar();
  const avatarSpeakRef = useRef<AvatarSpeakFn | null>(null);
  const pendingSpeechRef = useRef<string | null>(null);
  const handleSpeakReady = useCallback((speak: AvatarSpeakFn | null) => {
    avatarSpeakRef.current = speak;
    if (speak && pendingSpeechRef.current) {
      speak(pendingSpeechRef.current);
      pendingSpeechRef.current = null;
    }
  }, []);
  const handleAssistantSpeech = useCallback(
    (text: string) => {
      if (!avatar.wantsAvatar) return;
      if (avatarSpeakRef.current) {
        avatarSpeakRef.current(text);
      } else {
        pendingSpeechRef.current = text;
      }
    },
    [avatar.wantsAvatar],
  );
  const { session, messages, phase, error, sendMessage, isReady, isThinking } = useAdvisorChat({
    onAssistantSpeech: handleAssistantSpeech,
  });
  const [input, setInput] = useState('');
  const endRef = useRef<HTMLDivElement>(null);

  const videoMode = avatar.wantsAvatar || avatar.starting || Boolean(avatar.sessionToken);
  const viewportLayout = embedded || videoMode;

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

  const handleViewModeChange = (mode: 'chat' | 'video') => {
    if (mode === 'video') {
      void avatar.turnOn();
    } else {
      avatar.requestOff();
    }
  };

  const loading = phase === 'loading_session';
  const viewMode: 'chat' | 'video' = videoMode ? 'video' : 'chat';

  const switchControl = (
    <ChatVideoSwitch
      mode={viewMode}
      onModeChange={handleViewModeChange}
      loading={avatar.starting}
      disabled={loading}
      variant={videoMode ? 'overlay' : 'surface'}
    />
  );

  const messageList = (
    <>
      {loading && (
        <div
          className={`flex flex-1 items-center justify-center gap-2 text-sm ${
            viewportLayout && videoMode ? 'text-white/70' : 'text-content-muted'
          }`}
        >
          <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
          {t('advisor.loading')}
        </div>
      )}

      {!loading && messages.length === 0 && (
        <div className="flex flex-col gap-3 py-6">
          <p
            className={`text-center text-sm ${
              viewportLayout && videoMode ? 'text-white/70' : 'text-content-sub'
            }`}
          >
            {t('advisor.empty')}
          </p>
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => handleSuggestion(key)}
                disabled={!isReady || isThinking}
                className={
                  viewportLayout && videoMode
                    ? `${CRYSTAL_DARK_CLASS} cursor-pointer rounded-full px-4 py-2 text-sm text-white/90 transition-colors hover:bg-black/30 disabled:cursor-not-allowed disabled:opacity-40`
                    : 'border-outline bg-surface-sub text-content hover:bg-surface cursor-pointer rounded-full border px-4 py-2 text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-40'
                }
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
          overlay={viewportLayout && videoMode}
          onChipClick={(label) => void sendMessage(label)}
        >
          {message.uiPayload.length > 0 && <UIPayloadRenderer components={message.uiPayload} />}
        </MessageBubble>
      ))}
      <div ref={endRef} />
    </>
  );

  const alerts = (
    <>
      {(error || avatar.error) && (
        <div
          role="alert"
          className={`text-error border-error/30 bg-error/10 rounded-2xl border px-4 py-3 text-sm ${
            viewportLayout && videoMode ? 'mx-3 mb-2' : 'mb-2'
          }`}
        >
          {error ?? avatar.error}
        </div>
      )}

      {avatar.endedByServer && !avatar.error && (
        <div
          role="status"
          className={`text-warning border-warning/30 bg-warning/10 rounded-2xl border px-4 py-3 text-sm ${
            viewportLayout && videoMode ? 'mx-3 mb-2' : 'mb-2'
          }`}
        >
          {t('advisor.avatar_ended')}
        </div>
      )}
    </>
  );

  const composer = (
    <form
      onSubmit={handleSubmit}
      className={
        viewportLayout && videoMode
          ? `${CRYSTAL_DARK_STRONG_CLASS} mx-3 mb-3 flex items-center gap-2 rounded-full px-3 py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]`
          : 'border-outline bg-surface-sub flex items-center gap-1 rounded-full border p-1'
      }
    >
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
        className={
          viewportLayout && videoMode
            ? 'min-h-10 flex-1 bg-transparent px-2 text-sm text-white placeholder:text-white/70 focus:outline-none disabled:opacity-50'
            : 'placeholder:text-content-muted min-h-11 flex-1 rounded-full bg-transparent px-4 text-sm focus:outline-none disabled:opacity-50'
        }
      />
      {viewportLayout && videoMode ? (
        <>
          <button
            type="submit"
            disabled={!isReady || isThinking || !input.trim()}
            className={`${CRYSTAL_DARK_CLASS} flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full text-white/90 transition-opacity hover:bg-black/30 disabled:cursor-not-allowed disabled:opacity-40`}
            title={t('advisor.send')}
          >
            {isThinking ? (
              <Loader2
                className="h-4 w-4 animate-spin motion-reduce:animate-none"
                aria-hidden="true"
              />
            ) : (
              <Send className="h-4 w-4" aria-hidden="true" />
            )}
            <span className="sr-only">{t('advisor.send')}</span>
          </button>
          <button
            type="button"
            onClick={() => handleViewModeChange('chat')}
            className={`${CRYSTAL_DARK_CLASS} flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full text-white/90 transition-colors hover:bg-black/30`}
            title={t('advisor.mode_chat')}
          >
            <X className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">{t('advisor.mode_chat')}</span>
          </button>
        </>
      ) : (
        <button
          type="submit"
          disabled={!isReady || isThinking || !input.trim()}
          className="bg-filled-dark text-filled-dark-fg flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full transition-opacity disabled:cursor-not-allowed disabled:opacity-40"
          title={t('advisor.send')}
        >
          {isThinking ? (
            <Loader2
              className="h-4 w-4 animate-spin motion-reduce:animate-none"
              aria-hidden="true"
            />
          ) : (
            <Send className="h-4 w-4" aria-hidden="true" />
          )}
          <span className="sr-only">{t('advisor.send')}</span>
        </button>
      )}
    </form>
  );

  if (viewportLayout && videoMode) {
    return (
      <AppShell embedded={embedded || videoMode}>
        <div className="relative flex h-full min-h-0 w-full flex-col overflow-hidden">
          {avatar.sessionToken && (
            <div className="absolute inset-0 size-full">
              <AvatarPanel
                key={avatar.sessionToken}
                sessionToken={avatar.sessionToken}
                active={avatar.wantsAvatar}
                onEnded={avatar.handleSessionEnded}
                onSpeakReady={handleSpeakReady}
              />
            </div>
          )}

          {!avatar.sessionToken && avatar.starting && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black">
              <Loader2
                className="h-6 w-6 animate-spin text-white/80 motion-reduce:animate-none"
                aria-hidden="true"
              />
              <p className="text-sm text-white/80">{t('advisor.avatar_starting')}</p>
            </div>
          )}

          <div className="pointer-events-none relative z-10 flex justify-center px-4 pt-[max(0.75rem,env(safe-area-inset-top))]">
            <div className="pointer-events-auto">{switchControl}</div>
          </div>

          <section
            aria-label={t('advisor.title')}
            className="relative z-10 mt-auto flex max-h-[48dvh] min-h-0 flex-col"
          >
            {session && (
              <p className="mx-4 mb-2 text-xs text-white/60">
                {t('advisor.greeting', { name: session.client.first_name })}
              </p>
            )}

            <div
              role="log"
              aria-live="polite"
              className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-3 py-2"
            >
              {messageList}
            </div>

            {alerts}
            {composer}
          </section>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell embedded={embedded}>
      <div
        className={
          viewportLayout
            ? 'flex h-full min-h-0 flex-1 flex-col overflow-hidden'
            : 'mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 p-4 sm:p-6'
        }
      >
        <section
          aria-label={t('advisor.title')}
          className={
            viewportLayout ? 'flex min-h-0 flex-1 flex-col' : 'flex min-h-0 flex-1 flex-col gap-4'
          }
        >
          <header
            className={
              viewportLayout
                ? 'flex justify-center px-4 pt-[max(0.75rem,env(safe-area-inset-top))] pb-3'
                : 'border-outline flex flex-col gap-3 border-b pb-4'
            }
          >
            {viewportLayout ? (
              switchControl
            ) : (
              <>
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <Sparkles className="text-content-sub h-5 w-5" aria-hidden="true" />
                    <h1 className="font-heading text-xl font-semibold">{t('advisor.title')}</h1>
                  </div>
                  {switchControl}
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
              </>
            )}
          </header>

          {viewportLayout && session && (
            <p className="text-content-muted px-4 text-xs">
              {t('advisor.greeting', { name: session.client.first_name })}
            </p>
          )}

          <div
            role="log"
            aria-live="polite"
            className={
              viewportLayout
                ? 'flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-2'
                : 'flex min-h-64 flex-1 flex-col gap-4 overflow-y-auto'
            }
          >
            {messageList}
          </div>

          {alerts}

          <div className={viewportLayout ? 'px-4 pb-[env(safe-area-inset-bottom)]' : undefined}>
            {composer}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
