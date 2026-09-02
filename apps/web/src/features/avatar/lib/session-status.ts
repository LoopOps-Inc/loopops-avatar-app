export type SessionState =
  | 'INACTIVE'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'DISCONNECTING'
  | 'DISCONNECTED';

export type ConnectionQuality = 'UNKNOWN' | 'GOOD' | 'BAD';

/** Accessible label for a live-session state. */
export function sessionStateLabel(state: SessionState, t: (key: string) => string): string {
  switch (state) {
    case 'CONNECTED':
      return t('live.state_connected');
    case 'CONNECTING':
      return t('live.connecting');
    case 'DISCONNECTING':
      return t('live.state_disconnecting');
    default:
      return t('live.state_offline');
  }
}

/** Status-dot classes for a live-session state. */
export function sessionStateClass(state: SessionState): string {
  switch (state) {
    case 'CONNECTED':
      return 'bg-success';
    case 'CONNECTING':
    case 'DISCONNECTING':
      return 'animate-pulse bg-warning motion-reduce:animate-none';
    default:
      return 'bg-content-muted';
  }
}
