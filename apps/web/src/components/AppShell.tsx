import type { ReactNode } from 'react';
import { useTranslation } from '@/i18n';

function usePathname(): string {
  if (typeof window === 'undefined') return '/';
  return window.location.pathname;
}

type AppShellProps = {
  children: ReactNode;
  /** Hide nav and fill the viewport. Use for webview embeds (`?embed=1`). */
  embedded?: boolean;
};

export function AppShell({ children, embedded = false }: AppShellProps) {
  const { t } = useTranslation();
  const pathname = usePathname();

  if (embedded) {
    return (
      <div className="bg-surface text-content flex h-dvh flex-col overflow-hidden">
        <main className="relative h-full min-h-0 flex-1 overflow-hidden">{children}</main>
      </div>
    );
  }

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
        </nav>
      </header>
      <main className="flex min-h-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
