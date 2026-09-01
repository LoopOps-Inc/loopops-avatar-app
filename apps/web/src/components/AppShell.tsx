import type { ReactNode } from 'react';

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="bg-surface text-content flex min-h-dvh flex-col">
      <main className="flex flex-1 flex-col">{children}</main>
    </div>
  );
}
