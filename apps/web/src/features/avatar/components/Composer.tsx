import {
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import { Send } from 'lucide-react';
import { useTranslation } from '@/i18n';

type ComposerProps = {
  disabled?: boolean;
  onSend: (message: string) => void;
};

const MAX_INPUT_HEIGHT_PX = 96;

export function Composer({ disabled = false, onSend }: ComposerProps) {
  const { t } = useTranslation();
  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const resizeInput = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, MAX_INPUT_HEIGHT_PX)}px`;
  }, []);

  useLayoutEffect(() => {
    resizeInput();
  }, [input, resizeInput]);

  const submit = () => {
    const trimmed = input.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setInput('');
    // Tapping the send button moves focus away on mobile, which collapses
    // the keyboard and drops the sheet. Re-focus to keep both alive.
    inputRef.current?.focus();
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submit();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex flex-1">
      <div className="border-outline bg-surface-sub flex min-h-14 w-full items-end rounded-[28px] border py-1.5 pr-1.5 pl-4">
        <label htmlFor="chat-input" className="sr-only">
          {t('live.input_label')}
        </label>
        <textarea
          ref={inputRef}
          id="chat-input"
          rows={1}
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('live.input_placeholder')}
          autoComplete="off"
          enterKeyHint="send"
          className="placeholder:text-content-muted text-content-muted bg-surface-sub max-h-24 min-h-6 min-w-0 flex-1 resize-none overflow-y-auto py-2 text-sm leading-5 focus:outline-none"
        />
        <button
          type="submit"
          disabled={disabled}
          aria-label={t('live.send')}
          className="bg-advisor-submit mb-0.5 flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full text-white transition-opacity duration-200 hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Send className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </form>
  );
}
