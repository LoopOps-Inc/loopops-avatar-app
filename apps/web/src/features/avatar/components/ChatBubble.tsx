import { Star } from 'lucide-react';
import { UIPayloadCards } from '@/features/advisor/components/ui-payload-cards';
import { useTranslation } from '@/i18n';
import type { ChatMessage } from '../types';

/** One transcript row: sender label, time, text and attached ui_payload cards. */
export function ChatBubble({ message }: { message: ChatMessage }) {
  const { locale } = useTranslation();
  const isUser = message.sender === 'user';
  const time = new Date(message.timestamp).toLocaleTimeString(locale === 'en' ? 'en-US' : 'es-MX', {
    hour: '2-digit',
    minute: '2-digit',
  });
  return (
    <div className={`flex gap-2 ${isUser ? 'justify-end' : 'items-end'}`}>
      {!isUser && (
        <div
          className="bg-chat-agent flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-(--brand-gold) p-2"
          aria-hidden="true"
        >
          <Star className="h-4 w-4 text-(--brand-gold)" />
        </div>
      )}
      <div className={`flex max-w-[85%] flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`w-full px-3.5 py-2 ${
            isUser
              ? 'rounded-bubble bg-chat-user text-chat-user-fg'
              : 'rounded-bubble rounded-bl-tail border-chat-agent-border bg-chat-agent text-content border'
          }`}
        >
          {message.message && (
            <p
              className={`text-[14px] wrap-break-word ${isUser ? 'text-chat-user-fg' : 'text-content'}`}
            >
              {message.message}
            </p>
          )}
          {message.uiComponents && message.uiComponents.length > 0 && (
            <UIPayloadCards components={message.uiComponents} />
          )}
        </div>
        <span className={`text-content-faint text-xs tabular-nums ${isUser ? 'pr-2' : 'pl-2'}`}>
          {time}
        </span>
      </div>
    </div>
  );
}
