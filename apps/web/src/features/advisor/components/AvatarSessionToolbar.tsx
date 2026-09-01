import type { ReactNode } from 'react';
import { SessionState, type ConnectionQuality } from '@heygen/liveavatar-web-sdk';
import { HeartPulse, Info, PhoneOff, Square, Volume2 } from 'lucide-react';
import { CRYSTAL_DARK_CLASS } from '@/components/Crystal';
import { useTranslation } from '@/i18n';
import { connectionQualityKey, sessionStateKey } from '@/i18n/liveavatar-labels';

type AvatarSessionToolbarProps = {
  sessionState: SessionState;
  isConnected: boolean;
  connectionQuality: ConnectionQuality;
  isAvatarTalking: boolean;
  onInterrupt: () => void;
  onKeepAlive: () => void;
  onClose: () => void;
  closeLabel: string;
  sandboxNotice?: string;
  className?: string;
};

function StatusPill({ children }: { children: ReactNode }) {
  return (
    <span
      className={`${CRYSTAL_DARK_CLASS} flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium tracking-wider text-white/80 uppercase`}
    >
      {children}
    </span>
  );
}

export function AvatarSessionToolbar({
  sessionState,
  isConnected,
  connectionQuality,
  isAvatarTalking,
  onInterrupt,
  onKeepAlive,
  onClose,
  closeLabel,
  sandboxNotice,
  className = '',
}: AvatarSessionToolbarProps) {
  const { t } = useTranslation();

  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 ${className}`}>
      <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
        <StatusPill>
          <span
            aria-hidden="true"
            className={`h-2 w-2 rounded-full ${
              isConnected
                ? 'bg-success'
                : sessionState === SessionState.CONNECTING
                  ? 'bg-warning animate-pulse motion-reduce:animate-none'
                  : 'bg-white/40'
            }`}
          />
          {t(sessionStateKey(sessionState))}
        </StatusPill>
        <StatusPill>{t(connectionQualityKey(connectionQuality))}</StatusPill>
        {isAvatarTalking && (
          <StatusPill>
            <Volume2
              className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none"
              aria-hidden="true"
            />
            {t('demo.avatar_talking')}
          </StatusPill>
        )}
        <button
          type="button"
          onClick={onInterrupt}
          disabled={!isConnected}
          className={`${CRYSTAL_DARK_CLASS} flex min-h-11 cursor-pointer items-center gap-2 rounded-full px-4 text-xs font-medium text-white/90 transition-colors hover:bg-black/30 disabled:cursor-not-allowed disabled:opacity-40`}
        >
          <Square className="h-3.5 w-3.5" aria-hidden="true" />
          {t('demo.interrupt')}
        </button>
        <button
          type="button"
          onClick={onKeepAlive}
          disabled={!isConnected}
          className={`${CRYSTAL_DARK_CLASS} flex min-h-11 cursor-pointer items-center gap-2 rounded-full px-4 text-xs font-medium text-white/90 transition-colors hover:bg-black/30 disabled:cursor-not-allowed disabled:opacity-40`}
        >
          <HeartPulse className="h-3.5 w-3.5" aria-hidden="true" />
          {t('demo.keep_alive')}
        </button>
        {sandboxNotice && (
          <span
            className={`${CRYSTAL_DARK_CLASS} flex max-w-full items-center gap-1.5 rounded-full px-3 py-1.5 text-[10px] text-white/70`}
          >
            <Info className="h-3 w-3 shrink-0" aria-hidden="true" />
            {sandboxNotice}
          </span>
        )}
      </div>
      <button
        type="button"
        onClick={onClose}
        aria-label={closeLabel}
        title={closeLabel}
        className="bg-error hover:bg-error/90 flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full text-white transition-colors duration-200"
      >
        <PhoneOff className="h-5 w-5" aria-hidden="true" />
      </button>
    </div>
  );
}
