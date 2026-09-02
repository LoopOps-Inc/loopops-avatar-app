import type { ReactNode } from 'react';

type AppShellProps = {
  children: ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  return (
    <div className="bg-surface text-content flex min-h-dvh flex-col">
      <main className="flex min-h-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
