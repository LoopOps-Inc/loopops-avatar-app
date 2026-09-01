import { useEffect, useRef, useState } from 'react';
import { ChevronUp, Loader2, Mic, MicOff } from 'lucide-react';
import { useTranslation } from '@/i18n';
import type { ChatMessage } from '../types';
import { Composer } from './Composer';

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
        className={`max-w-[85%] rounded-xl px-3.5 py-2 text-sm ${
          isUser
            ? 'rounded-br-sm border border-white/20 bg-white/20 text-white'
            : 'rounded-bl-sm border border-white/10 bg-black/60 text-white backdrop-blur-sm'
        }`}
      >
        <span className="mb-0.5 flex items-baseline justify-between gap-2">
          <span className="text-[11px] font-medium tracking-wide text-white/60 uppercase">
            {isUser ? t('live.user') : t('live.avatar')}
          </span>
          <span className="text-[10px] text-white/60 tabular-nums">{formatTime(message.timestamp)}</span>
        </span>
        <p className="leading-relaxed break-words">{message.message}</p>
      </div>
    </div>
  );
}

type ChatSheetProps = {
  messages: ChatMessage[];
  connected: boolean;
  voiceEnabled: boolean;
  isUserTalking: boolean;
  isMicMuted: boolean;
  micUnavailable: boolean;
  onSend: (message: string) => void;
  onToggleMic: () => void;
};

/**
 * Bottom chat sheet over the video stage: one unified input row (type AND
 * talk). Collapsed it shows the latest message; expanded the full transcript.
 * The sheet tracks visualViewport so the on-screen keyboard never covers the
 * composer (WebViews resize inconsistently).
 */
export function ChatSheet({
  messages,
  connected,
  voiceEnabled,
  isUserTalking,
  isMicMuted,
  micUnavailable,
  onSend,
  onToggleMic,
}: ChatSheetProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [keyboardInset, setKeyboardInset] = useState(0);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const lastMessage = messages[messages.length - 1];

  useEffect(() => {
    const viewport = window.visualViewport;
    if (!viewport) return;
    const update = () =>
      setKeyboardInset(Math.max(0, window.innerHeight - viewport.height - viewport.offsetTop));
    viewport.addEventListener('resize', update);
    viewport.addEventListener('scroll', update);
    update();
    return () => {
      viewport.removeEventListener('resize', update);
      viewport.removeEventListener('scroll', update);
    };
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div
      className="absolute inset-x-0 bottom-0 z-10 flex flex-col gap-3 px-4 pb-safe"
      style={{ transform: `translateY(-${keyboardInset}px)` }}
    >
      <div
        className="pointer-events-none absolute inset-x-0 bottom-0 -z-10 h-56 bg-gradient-to-t from-black/80 to-transparent"
        aria-hidden="true"
      />
      <div className="flex justify-center">
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-expanded={expanded}
          aria-label={t('live.transcript')}
          className="flex h-8 w-14 cursor-pointer items-center justify-center rounded-full border border-white/15 bg-black/40 text-white backdrop-blur-sm transition-colors duration-200 hover:bg-black/60"
        >
          <ChevronUp
            className={`h-4 w-4 text-white/80 transition-transform duration-200 ${
              expanded ? 'rotate-180' : ''
            }`}
            aria-hidden="true"
          />
        </button>
      </div>

      {expanded ? (
        <div
          role="log"
          aria-live="polite"
          aria-label={t('live.transcript')}
          className="flex max-h-[45dvh] flex-col gap-2 overflow-y-auto py-1"
        >
          {messages.length === 0 && (
            <p className="py-2 text-center text-xs text-white/60">{t('live.empty_chat')}</p>
          )}
          {messages.map((msg, i) => (
            <ChatBubble key={`${msg.timestamp}-${i}`} message={msg} />
          ))}
          <div ref={chatEndRef} />
        </div>
      ) : (
        <div className="flex min-h-7 items-center">
          {isUserTalking ? (
            <span className="flex w-full items-center justify-end gap-1.5 text-xs font-medium text-white/80">
              {t('live.listening')}
              <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
            </span>
          ) : (
            lastMessage && (
              <div
                className={`flex w-full ${
                  lastMessage.sender === 'user' ? 'justify-end' : 'justify-start'
                }`}
              >
                <p
                  className={`max-w-[85%] truncate rounded-full px-3.5 py-1.5 text-sm ${
                    lastMessage.sender === 'user'
                      ? 'bg-white/20 text-white'
                      : 'bg-black/50 text-white/90 backdrop-blur-sm'
                  }`}
                >
                  {lastMessage.message}
                </p>
              </div>
            )
          )}
        </div>
      )}

      {micUnavailable && (
        <p role="status" className="text-center text-xs text-white/60">
          {t('live.mic_unavailable')}
        </p>
      )}

      <div className="flex items-center gap-2">
        <Composer disabled={!connected} onSend={onSend} />
        {voiceEnabled && (
          <button
            type="button"
            aria-label={isMicMuted ? t('live.mic_unmute') : t('live.mic_mute')}
            aria-pressed={isMicMuted}
            onClick={onToggleMic}
            disabled={!connected}
            className={`flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full border backdrop-blur-sm transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-40 ${
              isMicMuted
                ? 'border-error/40 bg-error/90 text-white'
                : 'border-white/20 bg-black/50 text-white hover:bg-black/70'
            }`}
          >
            {isMicMuted ? (
              <MicOff className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Mic className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
        )}
      </div>
    </div>
  );
}
