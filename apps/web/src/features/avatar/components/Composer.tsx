import {
  useCallback,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from 'react';
import { Mic, Send, Square } from 'lucide-react';
import { useTranslation } from '@/i18n';

type ComposerProps = {
  disabled?: boolean;
  onSend: (message: string) => void;
  /** Show Talk / Stop + sound bars inside the pill (Cursor-style). */
  voiceEnabled?: boolean;
  isRecording?: boolean;
  /** 0–1 mic energy while recording; drives the in-composer sound bars. */
  micLevel?: number;
  onToggleMic?: () => void;
};

const MAX_INPUT_HEIGHT_PX = 96;
const SOUND_BAR_WEIGHTS = [0.45, 1, 0.7, 0.9, 0.55] as const;

function SoundBars({ level, active }: { level: number; active: boolean }) {
  return (
    <div className="flex h-5 items-end gap-0.5" aria-hidden="true" data-testid="mic-sound-bars">
      {SOUND_BAR_WEIGHTS.map((weight, index) => {
        const speaking = active && level > 0.04;
        const height = speaking
          ? Math.max(0.18, Math.min(1, level * weight + 0.08))
          : active
            ? 0.2 + (index % 2) * 0.08
            : 0.14;
        return (
          <span
            key={index}
            className="bg-content-muted w-0.5 rounded-full transition-[height] duration-75 ease-out"
            style={{ height: `${height * 100}%` }}
          />
        );
      })}
    </div>
  );
}

export function Composer({
  disabled = false,
  onSend,
  voiceEnabled = false,
  isRecording = false,
  micLevel = 0,
  onToggleMic,
}: ComposerProps) {
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
    <form onSubmit={handleSubmit} className="flex w-full">
      <div className="border-outline bg-surface-sub flex min-h-11 w-full items-center rounded-2xl border py-1 pr-1 pl-3">
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
          placeholder={isRecording ? t('live.listening') : t('live.input_placeholder')}
          autoComplete="off"
          enterKeyHint="send"
          className="placeholder:text-content-muted text-content-muted bg-surface-sub max-h-24 min-h-6 min-w-0 flex-1 resize-none overflow-y-auto py-1.5 text-sm leading-5 focus:outline-none"
        />
        <div className="flex shrink-0 items-center gap-1.5">
          {voiceEnabled && isRecording && <SoundBars level={micLevel} active={isRecording} />}
          {voiceEnabled && onToggleMic && (
            <button
              type="button"
              aria-label={isRecording ? t('live.mic_stop') : t('live.mic_talk')}
              aria-pressed={isRecording}
              onClick={onToggleMic}
              disabled={disabled}
              className={`flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border transition-colors duration-200 disabled:cursor-not-allowed disabled:opacity-40 ${
                isRecording
                  ? 'border-filled-dark bg-filled-dark text-error'
                  : 'text-filled-dark border-(--brand-gold) bg-(--brand-gold-bright) hover:brightness-95'
              }`}
            >
              {isRecording ? (
                <Square className="h-3.5 w-3.5 fill-current" aria-hidden="true" />
              ) : (
                <Mic className="h-4 w-4" aria-hidden="true" strokeWidth={2.25} />
              )}
            </button>
          )}
          <button
            type="submit"
            disabled={disabled}
            aria-label={t('live.send')}
            className="bg-advisor-submit flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-full text-white transition-opacity duration-200 hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            <Send className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>
    </form>
  );
}
