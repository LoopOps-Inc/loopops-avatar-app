/** Dev-only timeline logs for avatar speech debugging. Filter the console by `[avatar]`. */
export function avatarLog(phase: string, detail?: Record<string, unknown>): void {
  if (!import.meta.env.DEV) return;
  const ms = Math.round(performance.now());
  if (detail) {
    console.info(`[avatar ${ms}ms] ${phase}`, detail);
  } else {
    console.info(`[avatar ${ms}ms] ${phase}`);
  }
}
