import { ArrowRight, Loader2 } from 'lucide-react';
import { actinverAvatar } from '@/config/avatar';
import { useTranslation } from '@/i18n';

type StartScreenProps = {
  starting: boolean;
  error: string | null;
  endedByServer: boolean;
  onStart: () => void;
};

/** Pre-session CTA: compact banner to start a live conversation with Tino. */
export function StartScreen({ starting, error, endedByServer, onStart }: StartScreenProps) {
  const { t } = useTranslation();

  return (
    <div className="bg-surface-sub flex h-full flex-col">
      <div className="flex-1" aria-hidden="true" />
      <div className="px-safe pb-safe flex flex-col gap-3 p-4">
        <button
          type="button"
          onClick={onStart}
          disabled={starting}
          aria-label={starting ? t('live.starting') : t('live.start')}
          className="bg-filled-dark flex w-full cursor-pointer items-center gap-4 rounded-2xl p-4 text-left shadow-lg transition-opacity duration-200 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <div className="bg-outline h-14 w-14 shrink-0 overflow-hidden rounded-full">
            <img
              src={actinverAvatar.previewImageUrl}
              alt=""
              className="h-full w-full object-cover"
            />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="font-heading text-lg font-semibold text-white">
              {t('live.start_banner_title')}
            </h1>
            <p className="text-advisor-submit-fg mt-0.5 text-sm font-medium">
              {t('live.subtitle')}
            </p>
          </div>
          <span
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-white/10"
            aria-hidden="true"
          >
            {starting ? (
              <Loader2 className="text-advisor-submit-fg h-5 w-5 animate-spin motion-reduce:animate-none" />
            ) : (
              <ArrowRight className="text-advisor-submit-fg h-5 w-5" strokeWidth={2.5} />
            )}
          </span>
        </button>
        {error && (
          <div
            role="alert"
            className="border-error/30 bg-error/10 text-error rounded-xs border px-4 py-3 text-sm"
          >
            {error}
          </div>
        )}
        {endedByServer && !error && (
          <div
            role="status"
            className="border-warning/30 bg-warning/10 text-warning rounded-xs border px-4 py-3 text-sm"
          >
            {t('live.ended_by_server')}
          </div>
        )}
      </div>
    </div>
  );
}
