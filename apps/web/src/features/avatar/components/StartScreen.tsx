import { AudioLines, Loader2, PhoneCall } from 'lucide-react';
import { useTranslation } from '@/i18n';

type StartScreenProps = {
  starting: boolean;
  error: string | null;
  endedByServer: boolean;
  onStart: () => void;
};

/** Pre-session hero: title, single start action, error and ended notices. */
export function StartScreen({ starting, error, endedByServer, onStart }: StartScreenProps) {
  const { t } = useTranslation();
  return (
    <div className="relative flex h-full flex-col items-center justify-center gap-5 p-6 pt-safe pb-safe">
      <div
        className="pointer-events-none absolute inset-0 bg-gradient-to-b from-white/5 via-black/40 to-black/80"
        aria-hidden="true"
      />
      <div className="relative flex w-full flex-col items-center gap-5 text-center">
        <div className="flex h-16 w-16 items-center justify-center rounded-full border border-white/20 bg-white/10">
          <AudioLines className="h-7 w-7 text-white" aria-hidden="true" />
        </div>
        <div>
          <h1 className="font-heading text-3xl font-semibold text-white">{t('live.title')}</h1>
          <p className="mt-1 text-sm text-white/70">{t('live.subtitle')}</p>
        </div>
        <button
          type="button"
          onClick={onStart}
          disabled={starting}
          className="flex min-h-12 w-full max-w-xs cursor-pointer items-center justify-center gap-2 rounded-cta bg-filled-dark px-8 text-base font-medium text-filled-dark-fg transition-opacity duration-200 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {starting ? (
            <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
          ) : (
            <PhoneCall className="h-5 w-5" aria-hidden="true" />
          )}
          {starting ? t('live.starting') : t('live.start')}
        </button>
        {error && (
          <div
            role="alert"
            className="w-full max-w-xs rounded-xs border border-error/30 bg-error/10 px-4 py-3 text-sm text-error"
          >
            {error}
          </div>
        )}
        {endedByServer && !error && (
          <div
            role="status"
            className="w-full max-w-xs rounded-xs border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning"
          >
            {t('live.ended_by_server')}
          </div>
        )}
      </div>
    </div>
  );
}
