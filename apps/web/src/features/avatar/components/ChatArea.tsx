import { useEffect, useRef } from 'react';
import { Loader2, Mic, MicOff } from 'lucide-react';
import { UIPayloadCards } from '@/features/advisor/components/ui-payload-cards';
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
            : 'rounded-bl-sm border border-white/10 bg-white/5 text-white backdrop-blur-sm'
        }`}
      >
        <span className="mb-0.5 flex items-baseline justify-between gap-2">
          <span className="text-[11px] font-medium tracking-wide text-white/60 uppercase">
            {isUser ? t('live.user') : t('live.avatar')}
          </span>
          <span className="text-[10px] text-white/60 tabular-nums">{formatTime(message.timestamp)}</span>
        </span>
        {message.message && <p className="leading-relaxed break-words">{message.message}</p>}
        {message.uiComponents && message.uiComponents.length > 0 && (
          <UIPayloadCards components={message.uiComponents} />
        )}
      </div>
    </div>
  );
}

type ChatAreaProps = {
  messages: ChatMessage[];
  connected: boolean;
  /** Live session still connecting: skeletons replace transcript and composer. */
  loading?: boolean;
  busy?: boolean;
  voiceEnabled: boolean;
  isUserTalking: boolean;
  isMicMuted: boolean;
  micUnavailable: boolean;
  onSend: (message: string) => void;
  onToggleMic: () => void;
};

/**
 * Scrollable chat transcript plus composer. Lives inside the avatar sheet:
 * the sheet's snap points control how much of this area is visible, so the
 * transcript is always rendered (no collapsed/expanded modes). While the
 * live session connects, skeletons stand in for the transcript and the
 * composer.
 */
export function ChatArea({
  messages,
  connected,
  loading = false,
  busy = false,
  voiceEnabled,
  isUserTalking,
  isMicMuted,
  micUnavailable,
  onSend,
  onToggleMic,
}: ChatAreaProps) {
  const { t } = useTranslation();
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2 px-4 pt-1 pb-safe">
      {loading ? (
        <div className="flex min-h-0 flex-1 flex-col gap-3 pt-2">
          <p className="flex items-center gap-2 text-xs font-medium text-white/70">
            <Loader2
              className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none"
              aria-hidden="true"
            />
            {t('live.connecting')}
          </p>
          <div className="flex flex-col gap-2" aria-hidden="true">
            <div className="h-9 w-3/5 animate-pulse rounded-xl bg-white/10 motion-reduce:animate-none" />
            <div className="ml-auto h-9 w-2/5 animate-pulse rounded-xl bg-white/10 motion-reduce:animate-none" />
            <div className="h-9 w-1/2 animate-pulse rounded-xl bg-white/10 motion-reduce:animate-none" />
          </div>
        </div>
      ) : (
        <div
          role="log"
          aria-live="polite"
          aria-label={t('live.transcript')}
          className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto py-1"
        >
          {messages.length === 0 && (
            <p className="py-2 text-center text-xs text-white/60">{t('live.empty_chat')}</p>
          )}
          {messages.map((msg, i) => (
            <ChatBubble key={`${msg.timestamp}-${i}`} message={msg} />
          ))}
          <div ref={chatEndRef} />
        </div>
      )}

      {isUserTalking && !loading && (
        <p className="flex items-center justify-end gap-1.5 text-xs font-medium text-white/80">
          {t('live.listening')}
        </p>
      )}
      {micUnavailable && (
        <p role="status" className="text-center text-xs text-white/60">
          {t('live.mic_unavailable')}
        </p>
      )}

      {loading ? (
        <div className="flex items-center gap-2" aria-hidden="true">
          <div className="h-11 flex-1 animate-pulse rounded-full border border-white/10 bg-white/10 motion-reduce:animate-none" />
          <div className="h-11 w-11 animate-pulse rounded-full bg-filled-dark/50 motion-reduce:animate-none" />
        </div>
      ) : (
        <div className="flex items-center gap-2">
          <Composer disabled={!connected || busy} onSend={onSend} />
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
      )}
    </div>
  );
}
