import { AudioLines, Maximize2, Minimize2, PhoneOff, Square } from 'lucide-react';
import { useTranslation } from '@/i18n';
import { StatusPill } from './StatusPill';

type SessionRailProps = {
  stateText: string;
  stateClass: string;
  showQualityPill: boolean;
  isAvatarTalking: boolean;
  isFullScreen: boolean;
  canEnd: boolean;
  onInterrupt: () => void;
  onToggleSnap: () => void;
  onEnd: () => void;
};

/**
 * Session header row inside the chat sheet: status pills on the left,
 * contextual actions (interrupt while speaking, snap toggle, end) on the
 * right. Living inside the sheet keeps every control reachable — vaul's
 * Radix dialog always hides outside content from the a11y tree.
 */
export function SessionRail({
  stateText,
  stateClass,
  showQualityPill,
  isAvatarTalking,
  isFullScreen,
  canEnd,
  onInterrupt,
  onToggleSnap,
  onEnd,
}: SessionRailProps) {
  const { t } = useTranslation();
  const actionButton =
    'flex h-10 w-10 cursor-pointer items-center justify-center rounded-full  bg-[#041e41] text-icon-muted transition-colors duration-200 hover:bg-outline/30';
  return (
    <div className="flex items-center justify-between gap-2 px-4 pt-2">
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <h2 className="font-heading truncate text-sm font-semibold text-black">
          {t('live.title')}
        </h2>
        {/* <StatusPill>
          <span aria-hidden="true" className={`h-2 w-2 rounded-full ${stateClass}`} />
          {stateText}
        </StatusPill>
        {showQualityPill && <StatusPill>{t('live.quality_poor')}</StatusPill>}
        {isAvatarTalking && (
          <StatusPill>
            <AudioLines
              className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none"
              aria-hidden="true"
            />
            {t('live.avatar_talking')}
          </StatusPill>
        )} */}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        {isAvatarTalking && (
          <button
            type="button"
            aria-label={t('live.interrupt')}
            onClick={onInterrupt}
            className={actionButton}
          >
            <Square className="h-4 w-4 fill-current" aria-hidden="true" />
          </button>
        )}
        <button
          type="button"
          aria-label={isFullScreen ? t('live.collapse') : t('live.expand')}
          aria-pressed={isFullScreen}
          onClick={onToggleSnap}
          className={actionButton}
        >
          {isFullScreen ? (
            <Minimize2 className="h-4 w-4 text-white" aria-hidden="true" />
          ) : (
            <Maximize2 className="h-4 w-4 text-white" aria-hidden="true" />
          )}
        </button>
        <button
          type="button"
          aria-label={t('live.end')}
          onClick={onEnd}
          disabled={!canEnd}
          className={`${actionButton} border-error/40 bg-error/90 hover:bg-error disabled:cursor-not-allowed disabled:opacity-40`}
        >
          <PhoneOff className="h-4 w-4 text-white" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
