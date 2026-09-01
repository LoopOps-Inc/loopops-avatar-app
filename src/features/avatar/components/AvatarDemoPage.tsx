import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { SessionState } from '@heygen/liveavatar-web-sdk';
import {
  HeartPulse,
  Info,
  Loader2,
  MessageSquare,
  Play,
  Send,
  Square,
  Volume2,
  X,
} from 'lucide-react';
import { AppShell } from '@/components/AppShell';
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
      <div
        className={`max-w-[85%] rounded-xs border px-3 py-2 text-sm ${
          isUser ? 'border-accent/20 bg-accent/10' : 'border-outline bg-surface'
        }`}
      >
        <span className="mb-0.5 flex items-baseline justify-between gap-2">
          <span className="text-[11px] font-medium tracking-wide text-content-muted uppercase">
            {isUser ? t('demo.user') : t('demo.avatar')}
          </span>
          <span className="text-[10px] text-content-muted tabular-nums">
            {formatTime(message.timestamp)}
          </span>
        </span>
        <p className="leading-relaxed break-words">{message.message}</p>
      </div>
    </div>
  );
}

function StatusPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-1.5 rounded-full bg-black/60 px-3 py-1.5 text-xs font-medium tracking-wider text-white/80 uppercase backdrop-blur-sm">
      {children}
    </span>
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

  const handleStop = () => {
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
    <div className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-3 p-4 sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row">
        <div className="relative flex-1 overflow-hidden rounded-sm bg-black">
          <video
            ref={videoRef}
            autoPlay
            playsInline
            className={`aspect-video w-full object-contain transition-opacity duration-300 ${
              isConnected ? 'opacity-100' : 'opacity-0'
            }`}
          />
          {!isConnected && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/60">
              <Loader2
                className="h-6 w-6 animate-spin text-white/80 motion-reduce:animate-none"
                aria-hidden="true"
              />
              <p className="text-sm text-white/80">{t('demo.connecting')}</p>
            </div>
          )}
          <div className="absolute top-3 left-3 flex flex-wrap items-center gap-2">
            <StatusPill>
              <span
                aria-hidden="true"
                className={`h-2 w-2 rounded-full ${
                  isConnected
                    ? 'bg-success'
                    : sessionState === SessionState.CONNECTING
                      ? 'animate-pulse bg-warning motion-reduce:animate-none'
                      : 'bg-white/40'
                }`}
              />
              {sessionState}
            </StatusPill>
            <StatusPill>{connectionQuality}</StatusPill>
            {isAvatarTalking && (
              <span className="flex items-center gap-1.5 rounded-full bg-black/60 px-3 py-1.5 text-xs font-medium text-white/80 backdrop-blur-sm">
                <Volume2
                  className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none"
                  aria-hidden="true"
                />
                {t('demo.avatar_talking')}
              </span>
            )}
          </div>
          <button
            type="button"
            onClick={handleStop}
            className="absolute top-3 right-3 flex min-h-11 cursor-pointer items-center gap-2 rounded-xs bg-error/90 px-4 text-sm font-medium text-white transition-colors duration-200 hover:bg-error"
          >
            <X className="h-4 w-4" aria-hidden="true" />
            {t('demo.end')}
          </button>
        </div>

        <section
          aria-label={t('demo.transcript')}
          className="flex w-full flex-col overflow-hidden rounded-sm border border-outline bg-surface-sub lg:w-80"
        >
          <div className="flex items-center gap-2 border-b border-outline p-3">
            <MessageSquare className="h-4 w-4 text-content-sub" aria-hidden="true" />
            <p className="text-sm font-medium">{t('demo.transcript')}</p>
          </div>
          <div
            role="log"
            aria-live="polite"
            className="flex max-h-60 flex-1 flex-col gap-2 overflow-y-auto p-3 lg:max-h-none"
          >
            {messages.length === 0 && (
              <p className="mt-4 text-center text-xs text-content-muted">
                {t('demo.empty_chat')}
              </p>
            )}
            {messages.map((msg, i) => (
              <ChatBubble key={`${msg.timestamp}-${i}`} message={msg} />
            ))}
            <div ref={chatEndRef} />
          </div>
          <form onSubmit={handleSend} className="flex gap-2 border-t border-outline p-3">
            <label htmlFor="chat-input" className="sr-only">
              {t('demo.input_label')}
            </label>
            <input
              id="chat-input"
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={t('demo.input_placeholder')}
              autoComplete="off"
              className="min-h-11 flex-1 rounded-xs border border-outline bg-surface px-4 text-sm text-content transition-colors placeholder:text-content-muted focus:border-content-sub focus:outline-none"
            />
            <button
              type="submit"
              disabled={!isConnected}
              className="flex min-h-11 cursor-pointer items-center gap-2 rounded-cta bg-filled-dark px-5 text-sm font-medium text-filled-dark-fg transition-opacity duration-200 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Send className="h-4 w-4" aria-hidden="true" />
              {t('demo.send')}
            </button>
          </form>
          <div className="flex flex-wrap gap-2 border-t border-outline p-3">
            <button
              type="button"
              onClick={() => void interrupt()}
              disabled={!isConnected}
              className="flex min-h-11 cursor-pointer items-center gap-2 rounded-cta border border-outline px-4 text-sm font-medium text-content transition-colors duration-200 hover:bg-surface disabled:cursor-not-allowed disabled:opacity-40"
            >
              <Square className="h-4 w-4" aria-hidden="true" />
              {t('demo.interrupt')}
            </button>
            <button
              type="button"
              onClick={() => void keepAlive()}
              disabled={!isConnected}
              className="flex min-h-11 cursor-pointer items-center gap-2 rounded-cta border border-outline px-4 text-sm font-medium text-content transition-colors duration-200 hover:bg-surface disabled:cursor-not-allowed disabled:opacity-40"
            >
              <HeartPulse className="h-4 w-4" aria-hidden="true" />
              {t('demo.keep_alive')}
            </button>
          </div>
        </section>
      </div>

      <p className="flex items-center justify-center gap-1.5 text-xs text-content-muted">
        <Info className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
        {t('demo.note')}
      </p>
    </div>
  );
}

export function AvatarDemoRoute() {
  const { t } = useTranslation();
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
    <AppShell>
      {!sessionToken ? (
        <div className="flex flex-1 items-center justify-center p-4 sm:p-6">
          <div className="w-full max-w-md">
            <div className="overflow-hidden rounded-sm border border-outline bg-surface-sub">
              <div className="flex aspect-video items-center justify-center bg-filled-dark">
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
                  <p className="mt-1 text-sm text-content-sub">{t('demo.subtitle')}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleStart()}
                  disabled={starting}
                  className="flex min-h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-cta bg-filled-dark px-8 text-base font-medium text-filled-dark-fg transition-opacity duration-200 disabled:cursor-not-allowed disabled:opacity-50"
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
                className="mt-4 rounded-xs border border-error/30 bg-error/10 px-4 py-3 text-sm text-error"
              >
                {error}
              </div>
            )}
            {endedByServer && !error && (
              <div
                role="status"
                className="mt-4 rounded-xs border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
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
