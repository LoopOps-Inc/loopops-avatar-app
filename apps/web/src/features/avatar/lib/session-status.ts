import { SessionState } from '@heygen/liveavatar-web-sdk';
import type { SessionState as SessionStateType } from '@heygen/liveavatar-web-sdk';

/** Accessible label for a live-session state. */
export function sessionStateLabel(state: SessionStateType, t: (key: string) => string): string {
  switch (state) {
    case SessionState.CONNECTED:
      return t('live.state_connected');
    case SessionState.CONNECTING:
      return t('live.connecting');
    case SessionState.DISCONNECTING:
      return t('live.state_disconnecting');
    default:
      return t('live.state_offline');
  }
}

/** Status-dot classes for a live-session state. */
export function sessionStateClass(state: SessionStateType): string {
  switch (state) {
    case SessionState.CONNECTED:
      return 'bg-success';
    case SessionState.CONNECTING:
    case SessionState.DISCONNECTING:
      return 'animate-pulse bg-warning motion-reduce:animate-none';
    default:
      return 'bg-content-muted';
  }
}
