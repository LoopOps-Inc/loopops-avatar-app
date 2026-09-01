import { UIPayloadCards } from '@/features/advisor/components/ui-payload-cards';
import { useTranslation } from '@/i18n';
import type { ChatMessage } from '../types';

function formatTime(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString('es-MX', {
    hour: '2-digit',
    minute: '2-digit',
  });
}

/** One transcript row: sender label, time, text and attached ui_payload cards. */
export function ChatBubble({ message }: { message: ChatMessage }) {
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
          <span className="text-[10px] text-white/60 tabular-nums">
            {formatTime(message.timestamp)}
          </span>
        </span>
        {message.message && <p className="leading-relaxed break-words">{message.message}</p>}
        {message.uiComponents && message.uiComponents.length > 0 && (
          <UIPayloadCards components={message.uiComponents} />
        )}
      </div>
    </div>
  );
}
