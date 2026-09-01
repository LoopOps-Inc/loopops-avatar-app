import type { RefObject } from 'react';
import { Loader2 } from 'lucide-react';
import { useTranslation } from '@/i18n';

type AvatarVideoSurfaceProps = {
  videoRef: RefObject<HTMLVideoElement | null>;
  isConnected: boolean;
};

export function AvatarVideoSurface({ videoRef, isConnected }: AvatarVideoSurfaceProps) {
  const { t } = useTranslation();

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
          <p className="text-sm text-white/80">{t('advisor.avatar_connecting')}</p>
        </div>
      )}
    </div>
  );
}
