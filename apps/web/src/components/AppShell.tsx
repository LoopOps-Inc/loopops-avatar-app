import type { ReactNode } from 'react';

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-surface text-content">
      <main className="flex flex-1 flex-col">{children}</main>
    </div>
  );
}
