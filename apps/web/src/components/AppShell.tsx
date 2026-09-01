import type { ReactNode } from 'react';
import { useTranslation } from '@/i18n';

function usePathname(): string {
  if (typeof window === 'undefined') return '/';
  return window.location.pathname;
}

export function AppShell({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const pathname = usePathname();

  return (
    <div className="bg-surface text-content flex min-h-dvh flex-col">
      <header className="border-outline bg-surface-sub border-b">
        <nav
          aria-label={t('nav.label')}
          className="mx-auto flex max-w-5xl items-center gap-1 px-4 py-2 sm:px-6"
        >
          <a
            href="/advisor"
            className={`rounded-xs px-3 py-2 text-sm font-medium transition-colors ${
              pathname === '/advisor'
                ? 'bg-filled-dark text-filled-dark-fg'
                : 'text-content-sub hover:bg-surface'
            }`}
          >
            {t('nav.advisor')}
          </a>
          <a
            href="/demo"
            className={`rounded-xs px-3 py-2 text-sm font-medium transition-colors ${
              pathname === '/demo'
                ? 'bg-filled-dark text-filled-dark-fg'
                : 'text-content-sub hover:bg-surface'
            }`}
          >
            {t('nav.demo')}
          </a>
        </nav>
      </header>
      <main className="flex flex-1 flex-col">{children}</main>
    </div>
  );
}
