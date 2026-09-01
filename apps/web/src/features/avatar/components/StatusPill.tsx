export function StatusPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="bg-surface-sub text-content-sub flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium tracking-wider uppercase">
      {children}
    </span>
  );
}
