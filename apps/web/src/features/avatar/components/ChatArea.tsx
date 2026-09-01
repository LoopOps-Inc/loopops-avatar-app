import { useEffect, useRef } from 'react';
import { Mic, MicOff } from 'lucide-react';
import { useTranslation } from '@/i18n';
import type { ChatMessage } from '../types';
import { ChatBubble } from './ChatBubble';
import { ChatLoadingList, ComposerSkeleton } from './ChatLoading';
import { Composer } from './Composer';

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
 * transcript is always rendered (no collapsed/expanded modes).
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
        <ChatLoadingList />
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
        <ComposerSkeleton />
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
