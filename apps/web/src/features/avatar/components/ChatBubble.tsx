import { UIPayloadCards } from '@/features/advisor/components/ui-payload-cards';
import { useTranslation } from '@/i18n';
import type { ChatMessage } from '../types';

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
            ? 'rounded-bubble bg-chat-user text-chat-user-fg'
            : 'rounded-bubble rounded-bl-tail border-chat-agent-border bg-chat-agent text-content border'
        }`}
      >
        {!isUser && (
          <span className="mb-1 flex items-center gap-1.5">
            <img src="/tino-icon.png" alt="" className="h-8 w-8 shrink-0" aria-hidden="true" />
            <span className="font-ui text-content text-sm font-bold">{t('live.avatar')}</span>
          </span>
        )}
        {message.message && (
          <p className="leading-6 break-words text-[#041E41]">{message.message}</p>
        )}
        {message.uiComponents && message.uiComponents.length > 0 && (
          <UIPayloadCards components={message.uiComponents} />
        )}
      </div>
      <span className={`text-content-small text-xs tabular-nums ${isUser ? 'pr-2' : 'pl-2'}`}>
        {time}
      </span>
    </div>
  );
}
