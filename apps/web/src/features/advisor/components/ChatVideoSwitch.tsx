import { Loader2 } from 'lucide-react';
import { useTranslation } from '@/i18n';
import { CRYSTAL_DARK_CLASS } from '@/components/Crystal';

type ViewMode = 'chat' | 'video';

type ChatVideoSwitchProps = {
  mode: ViewMode;
  onModeChange: (mode: ViewMode) => void;
  loading?: boolean;
  disabled?: boolean;
  /** Overlay sits on video. Surface sits on the page. */
  variant?: 'surface' | 'overlay';
};

export function ChatVideoSwitch({
  mode,
  onModeChange,
  loading = false,
  disabled = false,
  variant = 'surface',
}: ChatVideoSwitchProps) {
  const { t } = useTranslation();
  const overlay = variant === 'overlay';

  return (
    <div
      role="group"
      aria-label={t('advisor.view_mode_label')}
      className={`relative grid grid-cols-2 rounded-full p-1 ${
        overlay ? CRYSTAL_DARK_CLASS : 'border-outline bg-surface-sub border'
      }`}
    >
      <span
        aria-hidden="true"
        className={`pointer-events-none absolute inset-y-1 left-1 w-[calc(50%-0.25rem)] rounded-full transition-transform duration-200 ease-out motion-reduce:transition-none ${
          overlay ? 'bg-overlay-thumb' : 'bg-filled-dark'
        }`}
        style={{ transform: mode === 'video' ? 'translateX(100%)' : 'translateX(0)' }}
      />
      {(['chat', 'video'] as const).map((option) => {
        const active = mode === option;
        const isVideo = option === 'video';

        return (
          <button
            key={option}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled || (isVideo && loading)}
            onClick={() => onModeChange(option)}
            className={`relative z-10 min-h-11 min-w-[4.5rem] cursor-pointer rounded-full px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              active
                ? overlay
                  ? 'text-overlay-thumb-fg'
                  : 'text-filled-dark-fg'
                : overlay
                  ? 'text-white/80 hover:text-white'
                  : 'text-content-sub hover:text-content'
            }`}
          >
            {isVideo && loading ? (
              <span className="inline-flex items-center justify-center gap-1.5">
                <Loader2
                  className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none"
                  aria-hidden="true"
                />
                <span className="sr-only">{t('advisor.avatar_starting')}</span>
              </span>
            ) : (
              t(option === 'chat' ? 'advisor.mode_chat' : 'advisor.mode_video')
            )}
          </button>
        );
      })}
    </div>
  );
}
