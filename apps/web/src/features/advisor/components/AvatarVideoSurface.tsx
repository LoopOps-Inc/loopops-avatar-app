import type { RefObject } from 'react';
import { SessionState, type ConnectionQuality } from '@heygen/liveavatar-web-sdk';
import { Loader2 } from 'lucide-react';
import { useTranslation } from '@/i18n';
import { AvatarSessionToolbar } from './AvatarSessionToolbar';

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
        <div className="absolute top-3 right-3 left-3">
          <AvatarSessionToolbar
            sessionState={sessionState}
            isConnected={isConnected}
            connectionQuality={connectionQuality}
            isAvatarTalking={isAvatarTalking}
            onInterrupt={onInterrupt}
            onKeepAlive={onKeepAlive}
            onClose={onClose}
            closeLabel={closeLabel}
            sandboxNotice={sandboxNotice}
          />
        </div>
      )}
    </div>
  );
}
