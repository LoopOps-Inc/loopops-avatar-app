import { Loader2, PhoneCall } from 'lucide-react';
import { useTranslation } from '@/i18n';
import { TinoMark } from './TinoMark';

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
    <div className="pt-safe pb-safe relative flex h-full flex-col items-center justify-center gap-5 p-6">
      <div className="relative flex w-full flex-col items-center gap-4 text-center">
        <div className="bg-filled-dark flex w-full max-w-sm flex-col items-center gap-5 rounded-sm p-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-full border border-[color:var(--brand-gold-bright)]/30 bg-[color:var(--brand-gold-bright)]/10">
            <TinoMark className="h-8 w-8 text-[color:var(--brand-gold-bright)]" />
          </div>
          <div>
            <h1 className="font-heading text-2xl font-semibold text-white">{t('live.title')}</h1>
            <p className="font-ui mt-1.5 text-sm font-medium text-[color:var(--brand-gold-bright)]">
              {t('live.subtitle')}
            </p>
          </div>
          <button
            type="button"
            onClick={onStart}
            disabled={starting}
            className="rounded-cta flex min-h-12 w-full cursor-pointer items-center justify-center gap-2 bg-[color:var(--brand-gold-bright)] px-8 text-base font-medium text-[color:var(--brand-ink)] transition-opacity duration-200 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {starting ? (
              <Loader2
                className="h-5 w-5 animate-spin motion-reduce:animate-none"
                aria-hidden="true"
              />
            ) : null}
            {starting ? t('live.starting') : t('live.start')}
          </button>
        </div>
        {error && (
          <div
            role="alert"
            className="border-error/30 bg-error/10 text-error w-full max-w-sm rounded-xs border px-4 py-3 text-sm"
          >
            {error}
          </div>
        )}
        {endedByServer && !error && (
          <div
            role="status"
            className="border-warning/30 bg-warning/10 text-warning w-full max-w-sm rounded-xs border px-4 py-3 text-sm"
          >
            {t('live.ended_by_server')}
          </div>
        )}
      </div>
    </div>
  );
}
