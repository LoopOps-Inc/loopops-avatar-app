import { useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { Send } from 'lucide-react';
import { useTranslation } from '@/i18n';

type ComposerProps = {
  disabled?: boolean;
  onSend: (message: string) => void;
};

export function Composer({ disabled = false, onSend }: ComposerProps) {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = input.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setInput('');
    // Tapping the send button moves focus away on mobile, which collapses
    // the keyboard and drops the sheet. Re-focus to keep both alive.
    inputRef.current?.focus();
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-1">
      <div className="flex h-14 min-h-11 w-full items-center rounded-full border border-[#E2E4E9] bg-[#F7F8FA] pr-1.5 pl-4">
        <label htmlFor="chat-input" className="sr-only">
          {t('live.input_label')}
        </label>
        <input
          ref={inputRef}
          id="chat-input"
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t('live.input_placeholder')}
          autoComplete="off"
          enterKeyHint="send"
          className="placeholder:text-content-muted min-w-0 flex-1 border-[#E2E4E9] bg-transparent py-2 text-sm text-[#9398A5] focus:outline-none"
        />
        <button
          type="submit"
          disabled={disabled}
          aria-label={t('live.send')}
          className="bg-advisor-submit flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full text-white transition-opacity duration-200 hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </form>
  );
}
