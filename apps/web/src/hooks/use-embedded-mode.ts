import { useSyncExternalStore } from 'react';

function subscribe(callback: () => void): () => void {
  window.addEventListener('popstate', callback);
  return () => window.removeEventListener('popstate', callback);
}

function getSnapshot(): boolean {
  return new URLSearchParams(window.location.search).has('embed');
}

function getServerSnapshot(): boolean {
  return false;
}

/** True when loaded with `?embed=1` for host-app webview embeds. */
export function useEmbeddedMode(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
