import { Square } from 'lucide-react';
import { useTranslation } from '@/i18n';

type SessionControlsProps = {
  isAvatarTalking: boolean;
  onInterrupt: () => void;
};

/**
 * Contextual action rail over the video stage. Only the interrupt action
 * lives here and only while the avatar is speaking; session-level actions
 * (end) sit in the top bar and mic control sits in the voice bar.
 */
export function SessionControls({ isAvatarTalking, onInterrupt }: SessionControlsProps) {
  const { t } = useTranslation();
  if (!isAvatarTalking) return null;
  return (
    <div className="absolute top-1/2 right-3 z-20 flex -translate-y-1/2 flex-col gap-3">
      <button
        type="button"
        aria-label={t('live.interrupt')}
        onClick={onInterrupt}
        className="flex h-12 w-12 cursor-pointer items-center justify-center rounded-full border border-white/20 bg-black/50 text-white backdrop-blur-sm transition-colors duration-200 hover:bg-black/70"
      >
        <Square className="h-5 w-5 fill-current" aria-hidden="true" />
      </button>
    </div>
  );
}
