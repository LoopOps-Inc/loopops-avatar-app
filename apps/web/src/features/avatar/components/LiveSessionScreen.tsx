import { useCallback, useEffect, useRef, useState } from 'react';
import { AudioLines, Loader2, PhoneCall, PhoneOff } from 'lucide-react';
import { ConnectionQuality, SessionState } from '@heygen/liveavatar-web-sdk';
import type { SessionState as SessionStateType } from '@heygen/liveavatar-web-sdk';
import type { EmbedCommand, EmbedEvent } from '@loopops/contracts';
import { AppShell } from '@/components/AppShell';
import { useEmbedBridge } from '@/features/embed/hooks/use-embed-bridge';
import { useTranslation } from '@/i18n';
import { useLiveAvatarSession } from '../hooks/use-liveavatar-session';
import { ChatSheet } from './ChatSheet';
import { SessionControls } from './SessionControls';
import { StatusPill } from './StatusPill';

type PanelCommands = {
  stop: () => void;
  setMicMuted: (muted: boolean) => void;
};

type SessionPanelProps = {
  sessionToken: string;
  voiceEnabled: boolean;
  micUnavailable: boolean;
  onEnded: (reason: 'user' | 'server' | 'error') => void;
  registerCommands: (commands: PanelCommands | null) => void;
  onEvent: (event: EmbedEvent) => void;
};

function stateLabel(state: SessionStateType, t: (key: string) => string): string {
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

function SessionPanel({
  sessionToken,
  voiceEnabled,
  micUnavailable,
  onEnded,
  registerCommands,
  onEvent,
}: SessionPanelProps) {
  const { t } = useTranslation();
  const session = useLiveAvatarSession(sessionToken, { voiceChat: voiceEnabled });
  const videoRef = useRef<HTMLVideoElement>(null);

  const {
    sessionState,
    isStreamReady,
    connectionQuality,
    isAvatarTalking,
    isUserTalking,
    isMicMuted,
    messages,
    endReason,
    start,
    stop,
    attach,
    interrupt,
    sendMessage,
    setMicMuted,
  } = session;

  useEffect(() => {
    registerCommands({ stop: () => void stop(), setMicMuted });
    return () => registerCommands(null);
  }, [registerCommands, stop, setMicMuted]);

  useEffect(() => {
    if (sessionState === SessionState.INACTIVE) {
      void start();
    }
  }, [sessionState, start]);

  useEffect(() => {
    if (isStreamReady && videoRef.current) {
      attach(videoRef.current);
    }
  }, [isStreamReady, attach]);

  useEffect(() => {
    onEvent({ type: 'sessionState', payload: { state: sessionState, quality: connectionQuality } });
  }, [onEvent, sessionState, connectionQuality]);

  useEffect(() => {
    const last = messages[messages.length - 1];
    if (last) onEvent({ type: 'message', payload: last });
  }, [onEvent, messages]);

  useEffect(() => {
    if (endReason) {
      onEvent({ type: 'ended', payload: { reason: endReason } });
      onEnded(endReason);
    }
    // onEnded is a stable callback owned by the route component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endReason, onEvent]);

  const isConnected = sessionState === SessionState.CONNECTED;
  const isPoorQuality = connectionQuality === ConnectionQuality.BAD;

  return (
    <div className="relative h-full w-full overflow-hidden bg-black">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        className={`absolute inset-0 h-full w-full object-cover transition-opacity duration-300 ${
          isConnected ? 'opacity-100' : 'opacity-0'
        }`}
      />
      {!isConnected && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-black/60">
          <Loader2 className="h-6 w-6 animate-spin text-white/80 motion-reduce:animate-none" aria-hidden="true" />
          <p className="text-sm text-white/80">{t('live.connecting')}</p>
        </div>
      )}
      <div className="absolute inset-x-0 top-0 z-20 flex items-center justify-between gap-2 pt-safe px-4">
        <div className="flex flex-wrap items-center gap-2">
          <StatusPill>
            <span
              aria-hidden="true"
              className={`h-2 w-2 rounded-full ${
                isConnected
                  ? 'bg-success'
                  : sessionState === SessionState.CONNECTING ||
                      sessionState === SessionState.DISCONNECTING
                    ? 'animate-pulse bg-warning motion-reduce:animate-none'
                    : 'bg-white/40'
              }`}
            />
            {stateLabel(sessionState, t)}
          </StatusPill>
          {isPoorQuality && <StatusPill>{t('live.quality_poor')}</StatusPill>}
          {isAvatarTalking && (
            <StatusPill>
              <AudioLines className="h-3.5 w-3.5 animate-pulse motion-reduce:animate-none" aria-hidden="true" />
              {t('live.avatar_talking')}
            </StatusPill>
          )}
        </div>
        <button
          type="button"
          aria-label={t('live.end')}
          onClick={() => void stop()}
          disabled={!isConnected}
          className="flex h-11 w-11 shrink-0 cursor-pointer items-center justify-center rounded-full border border-error/40 bg-error/90 text-white backdrop-blur-sm transition-colors duration-200 hover:bg-error disabled:cursor-not-allowed disabled:opacity-40"
        >
          <PhoneOff className="h-5 w-5" aria-hidden="true" />
        </button>
      </div>
      <SessionControls isAvatarTalking={isAvatarTalking} onInterrupt={interrupt} />
      <ChatSheet
        messages={messages}
        connected={isConnected}
        voiceEnabled={voiceEnabled}
        isUserTalking={isUserTalking}
        isMicMuted={isMicMuted}
        micUnavailable={micUnavailable}
        onSend={(message) => sendMessage(message)}
        onToggleMic={() => setMicMuted(!isMicMuted)}
      />
    </div>
  );
}

export function LiveSessionRoute() {
  const { t } = useTranslation();
  const [sessionToken, setSessionToken] = useState<string | null>(null);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [micUnavailable, setMicUnavailable] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [endedByServer, setEndedByServer] = useState(false);
  const commandsRef = useRef<PanelCommands | null>(null);

  const handleEnded = useCallback(
    (reason: 'user' | 'server' | 'error') => {
      setSessionToken(null);
      setEndedByServer(reason === 'server');
    },
    [],
  );

  const handleStart = useCallback(async () => {
    setStarting(true);
    setError(null);
    setEndedByServer(false);
    let micAvailable = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      micAvailable = true;
    } catch {
      // No mic: the session still starts, typing-only.
    }
    setMicUnavailable(!micAvailable);
    try {
      const { createSandboxSessionToken } = await import('@/services/liveavatar-service');
      const token = await createSandboxSessionToken();
      setVoiceEnabled(micAvailable);
      setSessionToken(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('live.error_unknown'));
    } finally {
      setStarting(false);
    }
  }, [t]);

  const handleCommand = useCallback(
    (command: EmbedCommand) => {
      switch (command.type) {
        case 'start':
          if (!sessionToken) void handleStart();
          break;
        case 'stop':
          commandsRef.current?.stop();
          break;
        case 'setMuted':
          commandsRef.current?.setMicMuted(command.payload.muted);
          break;
      }
    },
    [handleStart, sessionToken],
  );

  const { emit } = useEmbedBridge(handleCommand);
  const registerCommands = useCallback((commands: PanelCommands | null) => {
    commandsRef.current = commands;
  }, []);
  const handlePanelEvent = useCallback(
    (event: Parameters<typeof emit>[0]) => {
      emit(event);
    },
    [emit],
  );

  return (
    <AppShell>
      <div className="flex min-h-dvh justify-center bg-surface-sub">
        <div className="relative h-dvh w-full overflow-hidden bg-black sm:my-auto sm:h-[min(853px,calc(100dvh-3rem))] sm:max-w-md sm:rounded-lg sm:border sm:border-outline">
          {!sessionToken ? (
            <div className="flex h-full flex-col items-center justify-center gap-5 p-6 pt-safe pb-safe">
              <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-white/5 via-black/40 to-black/80" aria-hidden="true" />
              <div className="relative flex w-full flex-col items-center gap-5 text-center">
                <div className="flex h-16 w-16 items-center justify-center rounded-full border border-white/20 bg-white/10">
                  <AudioLines className="h-7 w-7 text-white" aria-hidden="true" />
                </div>
                <div>
                  <h1 className="font-heading text-3xl font-semibold text-white">{t('live.title')}</h1>
                  <p className="mt-1 text-sm text-white/70">{t('live.subtitle')}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void handleStart()}
                  disabled={starting}
                  className="flex min-h-12 w-full max-w-xs cursor-pointer items-center justify-center gap-2 rounded-cta bg-filled-dark px-8 text-base font-medium text-filled-dark-fg transition-opacity duration-200 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {starting ? (
                    <Loader2 className="h-5 w-5 animate-spin motion-reduce:animate-none" aria-hidden="true" />
                  ) : (
                    <PhoneCall className="h-5 w-5" aria-hidden="true" />
                  )}
                  {starting ? t('live.starting') : t('live.start')}
                </button>
                {error && (
                  <div role="alert" className="w-full max-w-xs rounded-xs border border-error/30 bg-error/10 px-4 py-3 text-sm text-error">
                    {error}
                  </div>
                )}
                {endedByServer && !error && (
                  <div role="status" className="w-full max-w-xs rounded-xs border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning">
                    {t('live.ended_by_server')}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <SessionPanel
              key={sessionToken}
              sessionToken={sessionToken}
              voiceEnabled={voiceEnabled}
              micUnavailable={micUnavailable}
              onEnded={handleEnded}
              registerCommands={registerCommands}
              onEvent={handlePanelEvent}
            />
          )}
        </div>
      </div>
    </AppShell>
  );
}
