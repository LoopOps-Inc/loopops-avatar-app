import { UIPayloadCards } from '@/features/advisor/components/ui-payload-cards';
import { useTranslation } from '@/i18n';
import type { ChatMessage } from '../types';
import { TinoMark } from './TinoMark';

/** One transcript row: sender label, time, text and attached ui_payload cards. */
export function ChatBubble({ message }: { message: ChatMessage }) {
  const { t, locale } = useTranslation();
  const isUser = message.sender === 'user';
  const time = new Date(message.timestamp).toLocaleTimeString(locale === 'en' ? 'en-US' : 'es-MX', {
    hour: '2-digit',
    minute: '2-digit',
  });
  return (
    <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
      <div
        className={`max-w-[85%] px-3.5 py-2 ${
          isUser
            ? 'rounded-bubble bg-filled-dark text-filled-dark-fg'
            : 'rounded-bubble rounded-bl-tail border-outline-soft bg-surface text-content border'
        }`}
      >
        {!isUser && (
          <span className="mb-1 flex items-center gap-1.5">
            <TinoMark className="h-4 w-4 text-[color:var(--brand-gold)]" />
            <span className="font-ui text-content text-sm font-bold">{t('live.avatar')}</span>
          </span>
        )}
        {message.message && <p className="text-base leading-6 break-words">{message.message}</p>}
        {message.uiComponents && message.uiComponents.length > 0 && (
          <UIPayloadCards components={message.uiComponents} />
        )}
      </div>
      <span className={`text-content-sub text-xs tabular-nums ${isUser ? 'pr-2' : 'pl-2'}`}>
        {time}
      </span>
    </div>
  );
}
