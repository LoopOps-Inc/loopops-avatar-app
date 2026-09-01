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
    <div>
      {!isUser && (
        <span className="mb-1 flex items-center gap-1.5">
          <div className="h-8 rounded-full border border-[#927B2F] bg-[#fffdf5] p-2">
            <Star className="h-4 w-4 text-[#927B2F]" aria-hidden="true" />
          </div>
        </span>
      )}
      <div className={`flex flex-col gap-1 ${isUser ? 'items-end' : 'items-start'}`}>
        <div
          className={`max-w-[85%] px-3.5 py-2 ${
            isUser
              ? 'rounded-bubble bg-chat-user text-chat-user-fg'
              : 'rounded-bubble rounded-bl-tail border-chat-agent-border bg-chat-agent text-content border'
          }`}
        >
          {message.message && (
            <p className="leading-6 wrap-break-word text-[#041E41]">{message.message}</p>
          )}
          {message.uiComponents && message.uiComponents.length > 0 && (
            <UIPayloadCards components={message.uiComponents} />
          )}
        </div>
        <span className={`text-content-small text-xs tabular-nums ${isUser ? 'pr-2' : 'pl-2'}`}>
          {time}
        </span>
      </div>
    </div>
  );
}
