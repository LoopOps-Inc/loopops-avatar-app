import { useCallback, useEffect, useRef, useState } from 'react';
import type { EmbedCommand, EmbedEvent } from '@loopops/contracts';
import { EmbedBridge } from '../services/embed-bridge';

/**
 * Wires the EmbedBridge for the app lifetime. The bridge instance is created
 * once per mount via a lazy useState initializer (no side effects in the
 * constructor); the subscription lives in useEffect and returns the bridge's
 * own disposer. `onCommand` is kept in a ref so consumers may pass inline
 * closures without re-subscribing.
 */
export function useEmbedBridge(onCommand: (command: EmbedCommand) => void) {
  const commandRef = useRef(onCommand);

  useEffect(() => {
    commandRef.current = onCommand;
  }, [onCommand]);

  const [bridge] = useState(() => new EmbedBridge(window));

  useEffect(() => {
    return bridge.start((command) => commandRef.current(command));
  }, [bridge]);

  const emit = useCallback(
    (event: EmbedEvent) => {
      bridge.emit(event);
    },
    [bridge],
  );

  return { emit, isActive: bridge.isActive };
}
