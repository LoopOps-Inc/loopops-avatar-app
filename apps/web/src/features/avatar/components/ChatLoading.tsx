import { Loader2 } from 'lucide-react';
import { useTranslation } from '@/i18n';

/** Skeleton transcript shown while the live session connects. */
export function ChatLoadingList() {
  const { t } = useTranslation();
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 pt-2">
      <p className="text-content-small flex items-center gap-2 text-xs font-medium">
        <Loader2
          className="text-icon-muted h-3.5 w-3.5 animate-spin motion-reduce:animate-none"
          aria-hidden="true"
        />
        {t('live.connecting')}
      </p>
      <div className="flex flex-col gap-2" aria-hidden="true">
        <div className="rounded-bubble bg-surface-sub h-9 w-3/5 animate-pulse motion-reduce:animate-none" />
        <div className="rounded-bubble bg-surface-sub ml-auto h-9 w-2/5 animate-pulse motion-reduce:animate-none" />
        <div className="rounded-bubble bg-surface-sub h-9 w-1/2 animate-pulse motion-reduce:animate-none" />
      </div>
    </div>
  );
}

/** Skeleton composer shown while the live session connects. */
export function ComposerSkeleton() {
  return (
    <div
      className="border-outline bg-surface flex h-11 flex-1 items-center rounded-full border pr-1.5 pl-4"
      aria-hidden="true"
    >
      <div className="bg-surface-sub h-4 flex-1 animate-pulse rounded motion-reduce:animate-none" />
      <div className="bg-advisor-submit/50 h-9 w-9 shrink-0 animate-pulse rounded-full motion-reduce:animate-none" />
    </div>
  );
}
