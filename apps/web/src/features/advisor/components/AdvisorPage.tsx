import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import type { EmbedCommand, UIComponent } from '@loopops/contracts';
import { Loader2, Send, Sparkles, TriangleAlert, X } from 'lucide-react';
import { AppShell } from '@/components/AppShell';
import { useEmbeddedMode } from '@/hooks/use-embedded-mode';
import { useEmbedBridge } from '@/features/embed/hooks/use-embed-bridge';
import { getClientConfig } from '@/services/advisor-service';
import { useTranslation } from '@/i18n';
import { useAdvisorAvatar } from '../hooks/use-advisor-avatar';
import { useAdvisorChat } from '../hooks/use-advisor-chat';
import { AvatarPanel, type AvatarPanelCommands } from './AvatarPanel';
import { ChatVideoSwitch } from './ChatVideoSwitch';
import { UIPayloadRenderer } from './UIPayloadRenderer';

const CHIPS = ['advisor.chips.portfolio', 'advisor.chips.products', 'advisor.chips.retire'] as const;

const CONFIG_POLL_MS = 30_000;

const ADVISOR_CHIP_CLASS =
  'bg-advisor-cta text-advisor-cta-fg hover:opacity-90 cursor-pointer rounded-full px-4 py-2 text-sm transition-opacity disabled:cursor-not-allowed disabled:opacity-40';
const ADVISOR_ICON_BUTTON_CLASS =
  'bg-advisor-cta text-advisor-cta-fg flex shrink-0 cursor-pointer items-center justify-center rounded-full transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40';

function MessageBubble({
  role,
  text,
  streaming,
  overlay = false,
  children,
}: {
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
  overlay?: boolean;
  children?: ReactNode;
}) {
  const { t } = useTranslation();
  const isUser = role === 'user';

  if (overlay) {
    return (
      <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
        <div className="bg-surface text-content max-w-[min(100%,36rem)] rounded-2xl px-4 py-3">
          {text && (
            <p className="text-sm leading-relaxed">
              {text}
              {streaming && (
                <span className="bg-content-sub ml-0.5 inline-block h-4 w-0.5 animate-pulse motion-reduce:animate-none" />
              )}
            </p>
          )}
          {children && <div className="mt-3">{children}</div>}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className="border-outline bg-surface-sub text-content max-w-[min(100%,36rem)] rounded-sm border px-4 py-3">
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
      </div>
    </div>
  );
}

export function AdvisorRoute() {
  const { t } = useTranslation();
  const embedded = useEmbeddedMode();
  const avatar = useAdvisorAvatar();
  const avatarCommandsRef = useRef<AvatarPanelCommands | null>(null);
  const openVoiceTurnRef = useRef<string | null>(null);
  const {
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
    isReady,
    isThinking,
  } = useAdvisorChat();
  const [input, setInput] = useState('');
  const [killSwitchActive, setKillSwitchActive] = useState(false);
  const [killSwitchMessage, setKillSwitchMessage] = useState<string | null>(null);
  const [killSwitchDismissed, setKillSwitchDismissed] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const videoMode = avatar.wantsAvatar || avatar.starting || Boolean(avatar.session);
  const viewportLayout = embedded || videoMode;

  useEffect(() => {
    let cancelled = false;
    const poll = async () => {
      try {
        const config = await getClientConfig();
        if (!cancelled) {
          setKillSwitchActive(config.kill_switch);
          setKillSwitchMessage(config.kill_switch_message ?? null);
        }
      } catch {
        // Config polling is best effort.
      }
    };
    void poll();
    const timer = window.setInterval(() => void poll(), CONFIG_POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleVoiceUi = useCallback(
    (component: UIComponent) => {
      if (!openVoiceTurnRef.current) {
        openVoiceTurnRef.current = beginAssistantTurn();
      }
      appendAssistantUi(openVoiceTurnRef.current, component);
    },
    [appendAssistantUi, beginAssistantTurn],
  );

  const handleCaption = useCallback(
    (text: string) => {
      if (!text) return;
      setVoiceActivity('speaking');
      if (!openVoiceTurnRef.current) {
        openVoiceTurnRef.current = beginAssistantTurn();
      }
      setAssistantText(openVoiceTurnRef.current, text);
    },
    [beginAssistantTurn, setAssistantText, setVoiceActivity],
  );

  const handleVoiceActivity = useCallback(
    (activity: 'thinking' | 'speaking' | 'idle') => {
      setVoiceActivity(activity);
    },
    [setVoiceActivity],
  );

  const handleTurnComplete = useCallback(() => {
    const openId = openVoiceTurnRef.current;
    openVoiceTurnRef.current = null;
    if (openId) {
      endAssistantTurn(openId);
    }
    setVoiceActivity('idle');
  }, [endAssistantTurn, setVoiceActivity]);

  const handleTranscriptFinal = useCallback(
    (text: string) => {
      if (!text.trim()) return;
      appendUserMessage(text);
    },
    [appendUserMessage],
  );

  const handleAvatarEnded = useCallback(
    (reason: 'user' | 'server') => {
      handleTurnComplete();
      avatar.handleSessionEnded(reason);
    },
    [avatar, handleTurnComplete],
  );

  const handleAvatarConnectionError = useCallback(() => {
    setVoiceActivity('idle');
  }, [setVoiceActivity]);

  const handleViewModeChange = (mode: 'chat' | 'video') => {
    if (mode === 'video') {
      if (session) void avatar.turnOn(session.thread_id);
    } else {
      avatar.requestOff();
    }
  };

  const handleCommand = useCallback(
    (command: EmbedCommand) => {
      switch (command.type) {
        case 'start':
          if (session && !avatar.isActive && !avatar.starting) {
            void avatar.turnOn(session.thread_id);
          }
          break;
        case 'stop':
          avatar.requestOff();
          break;
        case 'setMuted':
          avatarCommandsRef.current?.setMic(!command.payload.muted);
          break;
      }
    },
    [avatar, session],
  );

  const { emit } = useEmbedBridge(handleCommand);

  useEffect(() => {
    emit({
      type: 'sessionState',
      payload: {
        state: avatar.isActive ? 'connected' : avatar.starting ? 'connecting' : 'disconnected',
        quality: 'unknown',
      },
    });
  }, [avatar.isActive, avatar.starting, emit]);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || !isReady || isThinking) return;
    void sendMessage(trimmed);
    setInput('');
  };

  const handleChip = (key: (typeof CHIPS)[number]) => {
    if (!isReady || isThinking) return;
    void sendMessage(t(key));
  };

  const loading = phase === 'loading_session';
  const viewMode: 'chat' | 'video' = videoMode ? 'video' : 'chat';

  const switchControl = (
    <ChatVideoSwitch
      mode={viewMode}
      onModeChange={handleViewModeChange}
      loading={avatar.starting}
      disabled={loading}
      variant="surface"
    />
  );

  const messageList = (
    <>
      {loading && (
        <div className="text-content-muted flex flex-1 items-center justify-center gap-2 text-sm">
          <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
          {t('advisor.loading')}
        </div>
      )}

      {!loading && messages.length === 0 && (
        <div className="flex flex-col gap-3 py-6">
          <p className="text-content-sub text-center text-sm">{t('advisor.empty')}</p>
          <div className="flex flex-wrap justify-center gap-2">
            {CHIPS.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => handleChip(key)}
                disabled={!isReady || isThinking}
                className={ADVISOR_CHIP_CLASS}
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
          overlay={viewportLayout && videoMode}
        >
          {message.uiPayload.length > 0 && <UIPayloadRenderer components={message.uiPayload} />}
        </MessageBubble>
      ))}

      {avatar.isActive && voiceActivity === 'thinking' && (
        <div className="flex justify-start">
          <div className="bg-surface text-content-sub flex items-center gap-2 rounded-2xl px-4 py-3 text-sm">
            <span className="bg-content-sub inline-block h-2 w-2 animate-pulse rounded-full motion-reduce:animate-none" />
            {t('advisor.thinking')}
          </div>
        </div>
      )}
      <div ref={endRef} />
    </>
  );

  const alerts = (
    <>
      {killSwitchActive && !killSwitchDismissed && (
        <div
          role="alert"
          className={`border-warning/30 bg-warning/10 text-warning flex items-start gap-2 rounded-2xl border px-4 py-3 text-sm ${
            viewportLayout && videoMode ? 'mx-3 mb-2' : 'mb-2'
          }`}
        >
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{killSwitchMessage || t('advisor.kill_switch')}</span>
          <button
            type="button"
            onClick={() => setKillSwitchDismissed(true)}
            aria-label={t('advisor.dismiss')}
            className="ml-auto cursor-pointer"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      )}

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
          ? 'border-outline bg-surface mx-3 mb-3 flex items-center gap-2 rounded-full border px-3 py-2 pb-[max(0.5rem,env(safe-area-inset-bottom))]'
          : 'border-outline bg-surface flex items-center gap-1 rounded-full border p-1'
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
            ? 'text-content placeholder:text-content-muted min-h-10 flex-1 bg-transparent px-2 text-sm focus:outline-none disabled:opacity-50'
            : 'text-content placeholder:text-content-muted min-h-11 flex-1 rounded-full bg-transparent px-4 text-sm focus:outline-none disabled:opacity-50'
        }
      />
      {viewportLayout && videoMode ? (
        <>
          <button
            type="submit"
            disabled={!isReady || isThinking || !input.trim()}
            className={`${ADVISOR_ICON_BUTTON_CLASS} h-10 w-10 bg-black text-white`}
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
            className={`${ADVISOR_ICON_BUTTON_CLASS} h-10 w-10`}
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
          className={`${ADVISOR_ICON_BUTTON_CLASS} h-11 w-11 bg-black text-white`}
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
      <div className="light">
        <AppShell embedded={embedded || videoMode}>
          <div className="relative flex h-full min-h-0 w-full flex-col overflow-hidden">
            {avatar.session && (
              <AvatarPanel
                key={avatar.session.avatar_session_id}
                session={avatar.session}
                onEnded={handleAvatarEnded}
                onTranscriptFinal={handleTranscriptFinal}
                onCaption={handleCaption}
                onUi={handleVoiceUi}
                onActivity={handleVoiceActivity}
                onTurnComplete={handleTurnComplete}
                onConnectionError={handleAvatarConnectionError}
                commandsRef={avatarCommandsRef}
              />
            )}

            {!avatar.session && avatar.starting && (
              <div className="bg-filled-dark absolute inset-0 flex flex-col items-center justify-center gap-3">
                <Loader2
                  className="text-filled-dark-fg h-6 w-6 animate-spin motion-reduce:animate-none"
                  aria-hidden="true"
                />
                <p className="text-filled-dark-fg text-sm">{t('advisor.avatar_starting')}</p>
              </div>
            )}

            <div className="pointer-events-none relative z-10 flex justify-center px-4 pt-[max(0.75rem,env(safe-area-inset-top))]">
              <div className="pointer-events-auto">{switchControl}</div>
            </div>

            <section
              aria-label={t('advisor.title')}
              className="relative z-10 mt-auto flex max-h-[48dvh] min-h-0 flex-col"
            >
              <div
                role="log"
                aria-live="polite"
                className="bg-surface text-content mx-3 flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto rounded-2xl px-3 py-2"
              >
                {messageList}
              </div>

              {alerts}
              {composer}
            </section>
          </div>
        </AppShell>
      </div>
    );
  }

  return (
    <div className="light flex min-h-0 flex-1 flex-col">
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
                </>
              )}
            </header>

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
    </div>
  );
}
