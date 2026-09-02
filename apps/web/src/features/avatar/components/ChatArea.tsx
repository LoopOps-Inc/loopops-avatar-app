import { Fragment, useEffect, useRef } from 'react';
import { useTranslation } from '@/i18n';
import { formatChatDayLabel } from '../lib/format-chat-day';
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
  isMicMuted: boolean;
  /** 0–1 mic energy while recording; drives the sound bars. */
  micLevel?: number;
  micUnavailable: boolean;
  onSend: (message: string) => void;
  onToggleMic: () => void;
};

function startOfDay(timestamp: number): number {
  const date = new Date(timestamp);
  date.setHours(0, 0, 0, 0);
  return date.getTime();
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
  isMicMuted,
  micLevel = 0,
  micUnavailable,
  onSend,
  onToggleMic,
}: ChatAreaProps) {
  const { t, locale } = useTranslation();
  const chatEndRef = useRef<HTMLDivElement>(null);
  const isRecording = !isMicMuted;

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
                  <p className="font-heading text-content-small py-1 text-left text-xs font-semibold">
                    {formatChatDayLabel(
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

      {micUnavailable && (
        <p role="status" className="text-content-small text-center text-xs">
          {t('live.mic_unavailable')}
        </p>
      )}

      {loading ? (
        <div className="flex w-full items-center">
          <ComposerSkeleton />
        </div>
      ) : (
        <Composer
          disabled={!connected || busy}
          onSend={onSend}
          voiceEnabled={voiceEnabled}
          isRecording={isRecording}
          micLevel={micLevel}
          onToggleMic={onToggleMic}
        />
      )}
    </div>
  );
}
