import { useTranslation } from '@/i18n';

type SuggestionChipsProps = {
  onSend: (message: string) => void;
  disabled?: boolean;
};

const SUGGESTION_KEYS = ['live.suggestion_1', 'live.suggestion_2', 'live.suggestion_3'] as const;

function SparkIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M8 1.5v3M8 11.5v3M1.5 8h3M11.5 8h3M3.75 3.75l2 2M10.25 10.25l2 2M12.25 3.75l-2 2M5.75 10.25l-2 2" />
    </svg>
  );
}

/** Topic chips that help the user open the conversation; tapping one sends it as the user message. */
export function SuggestionChips({ onSend, disabled = false }: SuggestionChipsProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap gap-2 py-2">
      {SUGGESTION_KEYS.map((key) => (
        <button
          key={key}
          type="button"
          disabled={disabled}
          onClick={() => onSend(t(key))}
          className="border-outline bg-filled-dark text-filled-dark-fg flex h-10 cursor-pointer items-center gap-2 rounded-full border px-4 text-sm transition-opacity duration-200 hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <SparkIcon className="h-4 w-4 shrink-0" />
          {t(key)}
        </button>
      ))}
    </div>
  );
}
