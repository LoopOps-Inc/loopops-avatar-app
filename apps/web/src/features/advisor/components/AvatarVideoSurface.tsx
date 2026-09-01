import type { RefObject } from 'react';
import { SessionState, type ConnectionQuality } from '@heygen/liveavatar-web-sdk';
import { HeartPulse, Info, Loader2, PhoneOff, Square, Volume2 } from 'lucide-react';
import { useTranslation } from '@/i18n';
import { connectionQualityKey, sessionStateKey } from '@/i18n/liveavatar-labels';
import { CRYSTAL_DARK_CLASS } from '@/components/Crystal';

type AvatarVideoSurfaceProps = {
  videoRef: RefObject<HTMLVideoElement | null>;
  sessionState: SessionState;
  isConnected: boolean;
  connectionQuality: ConnectionQuality;
  isAvatarTalking: boolean;
  onClose: () => void;
  onInterrupt: () => void;
  onKeepAlive: () => void;
  closeLabel: string;
  sandboxNotice?: string;
  /** Product overlay: video fills the screen, minimal chrome. */
  variant?: 'demo' | 'overlay';
};

function StatusPill({ children }: { children: React.ReactNode }) {
  return (
    <span
      className={`${CRYSTAL_DARK_CLASS} flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium tracking-wider text-white/80 uppercase`}
    >
      {children}
    </span>
  );
}

export function AvatarVideoSurface({
  videoRef,
  sessionState,
  isConnected,
  connectionQuality,
  isAvatarTalking,
  onClose,
  onInterrupt,
  onKeepAlive,
  closeLabel,
  sandboxNotice,
  variant = 'demo',
}: AvatarVideoSurfaceProps) {
  const { t } = useTranslation();
  const overlay = variant === 'overlay';

  return (
    <div className="relative h-full min-h-0 w-full flex-1 overflow-hidden bg-black">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        className={`absolute inset-0 size-full object-cover transition-opacity duration-300 ${
          isConnected ? 'opacity-100' : 'opacity-0'
        }`}
      />
      {!isConnected && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/60">
          <Loader2
            className="h-6 w-6 animate-spin text-white/80 motion-reduce:animate-none"
            aria-hidden="true"
          />
          <p className="text-sm text-white/80">{t('demo.connecting')}</p>
        </div>
      )}

      {!overlay && (
        <>
          <div className="absolute top-3 right-16 left-3 flex flex-wrap items-center gap-2">
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
              <span
                className={`${CRYSTAL_DARK_CLASS} flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium text-white/80`}
              >
                <Volume2
                  className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none"
                  aria-hidden="true"
                />
                {t('demo.avatar_talking')}
              </span>
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
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label={closeLabel}
            title={closeLabel}
            className="bg-error hover:bg-error/90 absolute top-3 right-3 flex h-11 w-11 cursor-pointer items-center justify-center rounded-full text-white transition-colors duration-200"
          >
            <PhoneOff className="h-5 w-5" aria-hidden="true" />
          </button>
          {sandboxNotice && (
            <p
              className={`${CRYSTAL_DARK_CLASS} pointer-events-none absolute bottom-[min(46dvh,20rem)] left-1/2 flex max-w-[90%] -translate-x-1/2 items-center justify-center gap-1.5 rounded-full px-3 py-1 text-center text-[10px] text-white/70`}
            >
              <Info className="h-3 w-3 shrink-0" aria-hidden="true" />
              {sandboxNotice}
            </p>
          )}
        </>
      )}

      {overlay && isAvatarTalking && (
        <div className="pointer-events-none absolute top-3 right-3">
          <StatusPill>
            <Volume2
              className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none"
              aria-hidden="true"
            />
            {t('demo.avatar_talking')}
          </StatusPill>
        </div>
      )}
    </div>
  );
}
