import { Fragment, useEffect, useRef } from 'react';
import { Mic, MicOff } from 'lucide-react';
import { useTranslation } from '@/i18n';
import type { ChatMessage } from '../types';
import { ChatBubble } from './ChatBubble';
import { ChatLoadingList, ComposerSkeleton } from './ChatLoading';
import { Composer } from './Composer';
import { SuggestionChips } from './SuggestionChips';

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

const DAY_MS = 86_400_000;

function startOfDay(timestamp: number): number {
  const date = new Date(timestamp);
  date.setHours(0, 0, 0, 0);
  return date.getTime();
}

function formatDayLabel(
  timestamp: number,
  locale: string,
  today: string,
  yesterday: string,
): string {
  const todayStart = startOfDay(Date.now());
  const diffDays = Math.round((todayStart - startOfDay(timestamp)) / DAY_MS);
  if (diffDays === 0) return today;
  if (diffDays === 1) return yesterday;
  const date = new Date(timestamp);
  return new Intl.DateTimeFormat(locale === 'en' ? 'en-US' : 'es-MX', {
    day: 'numeric',
    month: 'long',
    year: date.getFullYear() === new Date().getFullYear() ? undefined : 'numeric',
  }).format(date);
}

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
  const { t, locale } = useTranslation();
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // block: 'nearest' keeps the latest message visible without scrolling
    // ancestor containers (which would visibly nudge the sheet).
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [messages]);

  return (
    <div className="pb-safe flex min-h-0 flex-1 flex-col gap-2 px-4 pt-1">
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
            <SuggestionChips onSend={onSend} disabled={!connected || busy} />
          )}
          {messages.map((msg, i) => {
            const day = startOfDay(msg.timestamp);
            const prev = messages[i - 1];
            const showDaySeparator = !prev || startOfDay(prev.timestamp) !== day;
            return (
              <Fragment key={`${msg.timestamp}-${i}`}>
                {showDaySeparator && (
                  <p className="font-heading text-content-faint py-1 text-left text-xs font-semibold">
                    {formatDayLabel(
                      msg.timestamp,
                      locale,
                      t('live.day_today'),
                      t('live.day_yesterday'),
                    )}
                  </p>
                )}
                <ChatBubble message={msg} />
              </Fragment>
            );
          })}
          <div ref={chatEndRef} />
        </div>
      )}

      {isUserTalking && !loading && (
        <p className="text-content-sub flex items-center justify-end gap-1.5 text-xs font-medium">
          {t('live.listening')}
        </p>
      )}
      {micUnavailable && (
        <p role="status" className="text-content-faint text-center text-xs">
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
              className={`flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full border transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-40 ${
                isMicMuted
                  ? 'border-error/40 bg-error/90 text-white'
                  : 'border-outline bg-surface-sub text-content-sub hover:bg-outline/30'
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
