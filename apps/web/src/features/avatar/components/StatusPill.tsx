export function StatusPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="flex items-center gap-1.5 rounded-full bg-black/60 px-3 py-1.5 text-xs font-medium tracking-wider text-white/80 uppercase backdrop-blur-sm">
      {children}
    </span>
  );
}
