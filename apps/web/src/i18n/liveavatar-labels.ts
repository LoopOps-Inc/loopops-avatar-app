/** Map LiveAvatar SDK enum strings to i18n keys. */
export function sessionStateKey(state: string): string {
  const map: Record<string, string> = {
    INACTIVE: 'demo.session_inactive',
    CONNECTING: 'demo.session_connecting',
    CONNECTED: 'demo.session_connected',
    DISCONNECTED: 'demo.session_disconnected',
  };
  return map[state] ?? 'demo.session_unknown';
}

export function connectionQualityKey(quality: string): string {
  const map: Record<string, string> = {
    UNKNOWN: 'demo.quality_unknown',
    GOOD: 'demo.quality_good',
    POOR: 'demo.quality_poor',
    LOST: 'demo.quality_lost',
  };
  return map[quality] ?? 'demo.quality_unknown';
}
