import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { SessionState } from '@heygen/liveavatar-web-sdk';
import { Loader2, MessageSquare, Play, Send } from 'lucide-react';
import { AppShell } from '@/components/AppShell';
import { CRYSTAL_DARK_CLASS, CRYSTAL_DARK_STRONG_CLASS } from '@/components/Crystal';
import { AvatarVideoSurface } from '@/features/advisor/components/AvatarVideoSurface';
import { useEmbeddedMode } from '@/hooks/use-embedded-mode';
import { useTranslation } from '@/i18n';
import { useLiveAvatarSession } from '../hooks/use-liveavatar-session';
import type { ChatMessage } from '../types';

type AvatarSessionPanelProps = {
  sessionToken: string;
  onEnded: (reason: 'user' | 'server') => void;
};

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('es-MX', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function ChatBubble({ message }: { message: ChatMessage }) {
  const { t } = useTranslation();
  const isUser = message.sender === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`${CRYSTAL_DARK_CLASS} max-w-[85%] rounded-sm px-3 py-2 text-sm text-white`}>
        <span className="mb-0.5 flex items-baseline justify-between gap-2">
          <span className="text-[11px] font-medium tracking-wide text-white/50 uppercase">
            {isUser ? t('demo.user') : t('demo.avatar')}
          </span>
          <span className="text-[10px] text-white/40 tabular-nums">
            {formatTime(message.timestamp)}
          </span>
        </span>
        <p className="leading-relaxed wrap-break-word text-white/90">{message.message}</p>
      </div>
    </div>
  );
}

export function AvatarSessionPanel({ sessionToken, onEnded }: AvatarSessionPanelProps) {
  const { t } = useTranslation();
  const {
    sessionState,
    isStreamReady,
    connectionQuality,
    isAvatarTalking,
    messages,
    start,
    stop,
    attach,
    sendMessage,
    interrupt,
    keepAlive,
  } = useLiveAvatarSession(sessionToken);

  const videoRef = useRef<HTMLVideoElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const userStoppedRef = useRef(false);
  const [input, setInput] = useState('');

  useEffect(() => {
    if (sessionState === SessionState.DISCONNECTED) {
      onEnded(userStoppedRef.current ? 'user' : 'server');
    }
  }, [sessionState, onEnded]);

  useEffect(() => {
    if (sessionState === SessionState.INACTIVE) {
      void start();
    }
  }, [sessionState, start]);

  useEffect(() => {
    if (isStreamReady && videoRef.current) {
      attach(videoRef.current);
    }
  }, [attach, isStreamReady]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleClose = () => {
    userStoppedRef.current = true;
    void stop();
  };

  const handleSend = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    void sendMessage(trimmed);
    setInput('');
  };

  const isConnected = sessionState === SessionState.CONNECTED;

  return (
    <div className="relative flex h-full min-h-0 w-full flex-1 flex-col overflow-hidden">
      <AvatarVideoSurface
        videoRef={videoRef}
        sessionState={sessionState}
        isConnected={isConnected}
        connectionQuality={connectionQuality}
        isAvatarTalking={isAvatarTalking}
        onClose={handleClose}
        onInterrupt={() => void interrupt()}
        onKeepAlive={() => void keepAlive()}
        closeLabel={t('demo.end')}
        sandboxNotice={t('demo.note')}
      />

      <section
        aria-label={t('demo.transcript')}
        className={`${CRYSTAL_DARK_CLASS} absolute right-[max(1rem,env(safe-area-inset-right))] bottom-[max(1rem,env(safe-area-inset-bottom))] left-[max(1rem,env(safe-area-inset-left))] z-10 flex max-h-[42dvh] min-h-0 flex-col overflow-hidden rounded-md`}
      >
        <div className="flex items-center gap-2 px-4 py-3">
          <MessageSquare className="h-4 w-4 text-white/70" aria-hidden="true" />
          <p className="text-sm font-medium text-white/90">{t('demo.transcript')}</p>
        </div>
        <div
          role="log"
          aria-live="polite"
          className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto px-3 py-2"
        >
          {messages.length === 0 && (
            <p className="py-2 text-center text-xs text-white/60">{t('demo.empty_chat')}</p>
          )}
          {messages.map((msg, i) => (
            <ChatBubble key={`${msg.timestamp}-${i}`} message={msg} />
          ))}
          <div ref={chatEndRef} />
        </div>
        <form onSubmit={handleSend} className="flex items-center gap-2 px-3 pb-3">
          <label htmlFor="chat-input" className="sr-only">
            {t('demo.input_label')}
          </label>
          <div
            className={`${CRYSTAL_DARK_STRONG_CLASS} flex min-h-11 flex-1 items-center rounded-full px-4`}
          >
            <input
              id="chat-input"
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t('demo.input_placeholder')}
              autoComplete="off"
              className="min-h-11 flex-1 bg-transparent text-sm text-white placeholder:text-white/70 focus:outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={!isConnected}
            title={t('demo.send')}
            className={`${CRYSTAL_DARK_STRONG_CLASS} flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-white transition-opacity duration-200 hover:bg-black/40 disabled:cursor-not-allowed disabled:opacity-40`}
          >
            <Send className="h-4 w-4" aria-hidden="true" />
            <span className="sr-only">{t('demo.send')}</span>
          </button>
        </form>
      </section>
    </div>
  );
}

export function AvatarDemoRoute() {
  const { t } = useTranslation();
  const embedded = useEmbeddedMode();
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [endedByServer, setEndedByServer] = useState(false);

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    setEndedByServer(false);
    try {
      const { createSandboxSessionToken } = await import('@/services/liveavatar-service');
      const token = await createSandboxSessionToken();
      setSessionToken(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('demo.error_unknown'));
    } finally {
      setStarting(false);
    }
  };

  const handleEnded = (reason: 'user' | 'server') => {
    setSessionToken(null);
    setEndedByServer(reason === 'server');
  };

  return (
    <AppShell embedded={embedded || Boolean(sessionToken)}>
      {!sessionToken ? (
        <div className="flex flex-1 items-center justify-center p-4">
          <div className="w-full max-w-sm">
            <div className="border-outline bg-surface-sub overflow-hidden rounded-md border">
              <div className="bg-filled-dark flex aspect-video items-center justify-center">
                <span
                  aria-hidden="true"
                  className="flex h-16 w-16 items-center justify-center rounded-full border border-white/20 bg-white/10"
                >
                  <Play className="h-7 w-7 text-white" />
                </span>
              </div>
              <div className="flex flex-col gap-4 p-6">
                <div>
                  <h2 className="font-heading text-xl font-semibold">{t('demo.title')}</h2>
                  <p className="text-content-sub mt-1 text-sm">{t('demo.subtitle')}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleStart()}
                  disabled={starting}
                  className="bg-filled-dark text-filled-dark-fg flex min-h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-full px-8 text-base font-medium transition-opacity duration-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {starting && (
                    <Loader2
                      className="h-5 w-5 animate-spin motion-reduce:animate-none"
                      aria-hidden="true"
                    />
                  )}
                  {starting ? t('demo.starting') : t('demo.start')}
                </button>
              </div>
            </div>
            {error && (
              <div
                role="alert"
                className="border-error/30 bg-error/10 text-error mt-4 rounded-xs border px-4 py-3 text-sm"
              >
                {error}
              </div>
            )}
            {endedByServer && !error && (
              <div
                role="status"
                className="border-warning/30 bg-warning/10 text-warning mt-4 rounded-xs border px-4 py-3 text-sm"
              >
                {t('demo.ended_by_server')}
              </div>
            )}
          </div>
        </div>
      ) : (
        <AvatarSessionPanel sessionToken={sessionToken} onEnded={handleEnded} />
      )}
    </AppShell>
  );
}
