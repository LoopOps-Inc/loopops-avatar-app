import { useEffect, useState } from 'react';
import { actinverLogoUrl } from '@/config/avatar';

const SPLASH_MS = 1500;

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') {
    return false;
  }
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

type SplashOverlayProps = {
  skip?: boolean;
};

export function SplashOverlay({ skip = false }: SplashOverlayProps) {
  const [visible, setVisible] = useState(() => !skip && !prefersReducedMotion());

  useEffect(() => {
    if (!visible) return;
    const id = window.setTimeout(() => setVisible(false), SPLASH_MS);
    return () => window.clearTimeout(id);
  }, [visible]);

  if (!visible) return null;

  return (
    <div
      data-testid="auth-splash"
      className="bg-surface absolute inset-0 z-10 flex items-center justify-center"
      aria-hidden="true"
    >
      <img src={actinverLogoUrl} alt="" className="h-16 w-auto max-w-[70%] object-contain" />
    </div>
  );
}
