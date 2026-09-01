import type { CitationsPayload, WarningBannerPayload } from '@loopops/contracts';
import { AlertTriangle, ExternalLink, Info } from 'lucide-react';
import { useTranslation } from '@/i18n';

type WarningBannerProps = {
  payload: WarningBannerPayload;
};

export function WarningBanner({ payload }: WarningBannerProps) {
  const isWarning = payload.severity === 'warning';
  return (
    <div
      role="note"
      className={`flex items-start gap-2 rounded-xs border px-3 py-2 text-sm ${
        isWarning
          ? 'border-warning/30 bg-warning/10 text-warning'
          : 'border-outline bg-surface-sub text-content-sub'
      }`}
    >
      {isWarning ? (
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      ) : (
        <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
      )}
      <p>{payload.message}</p>
    </div>
  );
}

type CitationListProps = {
  payload: CitationsPayload;
};

export function CitationList({ payload }: CitationListProps) {
  const { t } = useTranslation();
  if (payload.items.length === 0) return null;

  return (
    <div className="border-outline bg-surface rounded-xs border p-4">
      <p className="text-content-muted text-xs font-medium tracking-wide uppercase">
        {t('advisor.sources_title')}
      </p>
      <ul className="mt-2 flex flex-col gap-2">
        {payload.items.map((item) => (
          <li key={`${item.title}-${item.published ?? ''}`}>
            {item.url ? (
              <a
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent flex items-start gap-1.5 text-sm hover:underline"
              >
                <ExternalLink className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                <span>
                  {item.title}
                  {item.published && (
                    <span className="text-content-muted"> · {item.published}</span>
                  )}
                </span>
              </a>
            ) : (
              <p className="text-sm">
                {item.title}
                {item.published && <span className="text-content-muted"> · {item.published}</span>}
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
