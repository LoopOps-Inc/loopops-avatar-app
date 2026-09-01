import { useCallback, useEffect, useRef, useState } from 'react';
import { AudioLines, Loader2, PhoneCall } from 'lucide-react';
import { ConnectionQuality, SessionState } from '@heygen/liveavatar-web-sdk';
import type { SessionState as SessionStateType } from '@heygen/liveavatar-web-sdk';
import type { EmbedCommand, EmbedEvent } from '@loopops/contracts';
import { AppShell } from '@/components/AppShell';
import { useAdvisorChat } from '@/features/advisor/hooks/use-advisor-chat';
import { useEmbedBridge } from '@/features/embed/hooks/use-embed-bridge';
import { useTranslation } from '@/i18n';
import { useLiveAvatarSession } from '../hooks/use-liveavatar-session';
import { ChatArea } from './ChatArea';
import { SessionRail } from './SessionRail';
import { SnapSheet } from './SnapSheet';

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

/** Snap fractions of the frame height: loading (compact), chat (video above), full screen. */
const SNAP_POINTS = [0.34, 0.62, 1];
const LOADING_SNAP = 0;
const CHAT_SNAP = 1;
const FULL_SNAP = 2;

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

/**
 * The avatar video is the base layer; the chat lives in a bottom snap sheet
 * (Motion) docked over it. Snap points control how much of the frame the
 * sheet occupies — the video shows through whatever space is left (the
 * full-screen snap covers it entirely, e.g. for future forms/firma). The
 * advisor mock owns the transcript; the avatar only speaks what the advisor
 * sends, so HeyGen transcriptions are not rendered.
 */
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
  const [snapIndex, setSnapIndex] = useState(LOADING_SNAP);

  const {
    sessionState,
    isStreamReady,
    connectionQuality,
    isAvatarTalking,
    isUserTalking,
    isMicMuted,
    endReason,
    start,
    stop,
    attach,
    interrupt,
    sendMessage,
    setMicMuted,
  } = session;

  const isConnected = sessionState === SessionState.CONNECTED;
  const speak = useCallback((text: string) => sendMessage(text), [sendMessage]);
  const advisor = useAdvisorChat({ speak, enabled: isConnected });

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
    const last = advisor.messages[advisor.messages.length - 1];
    if (last) {
      onEvent({
        type: 'message',
        payload: { sender: last.sender, message: last.message, timestamp: last.timestamp },
      });
    }
  }, [onEvent, advisor.messages]);

  useEffect(() => {
    if (endReason) {
      onEvent({ type: 'ended', payload: { reason: endReason } });
      onEnded(endReason);
    }
    // onEnded is a stable callback owned by the route component.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [endReason, onEvent]);

  const isPoorQuality = connectionQuality === ConnectionQuality.BAD;
  // Derived snap: compact while loading; once connected the effective snap is
  // at least the chat view (the loading snap is unreachable after connect).
  const effectiveSnap = !isConnected ? LOADING_SNAP : Math.max(snapIndex, CHAT_SNAP);
  const isFullScreen = effectiveSnap === FULL_SNAP;
  const visibleFraction = SNAP_POINTS[effectiveSnap] ?? 1;
  const stateClass = isConnected
    ? 'bg-success'
    : sessionState === SessionState.CONNECTING || sessionState === SessionState.DISCONNECTING
      ? 'animate-pulse bg-warning motion-reduce:animate-none'
      : 'bg-white/40';

  return (
    <>
      {/* Chat sheet: bottom docked, snap points control how much video is visible. */}
      <SnapSheet
        snaps={SNAP_POINTS}
        activeIndex={effectiveSnap}
        onActiveIndexChange={setSnapIndex}
        label={t('live.title')}
        above={
          <>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              className="h-full w-full object-cover"
            />
            {!isConnected && (
              <div
                role="status"
                aria-label={t('live.connecting')}
                className="absolute inset-0 flex items-center justify-center bg-gradient-to-b from-black/50 via-black/30 to-black/70"
              >
                <div className="flex h-16 w-16 animate-pulse items-center justify-center rounded-full border border-white/20 bg-white/5 motion-reduce:animate-none">
                  <Loader2
                    className="h-6 w-6 animate-spin text-white/80 motion-reduce:animate-none"
                    aria-hidden="true"
                  />
                </div>
              </div>
            )}
          </>
        }
      >
        <SessionRail
          stateText={stateLabel(sessionState, t)}
          stateClass={stateClass}
          showQualityPill={isPoorQuality}
          isAvatarTalking={isAvatarTalking}
          isFullScreen={isFullScreen}
          canEnd={isConnected}
          onInterrupt={interrupt}
          onToggleSnap={() => setSnapIndex(isFullScreen ? CHAT_SNAP : FULL_SNAP)}
          onEnd={() => void stop()}
        />
        <ChatArea
          messages={advisor.messages}
          connected={isConnected}
          loading={!isConnected}
          busy={advisor.isThinking}
          voiceEnabled={voiceEnabled}
          isUserTalking={isUserTalking}
          isMicMuted={isMicMuted}
          micUnavailable={micUnavailable}
          onSend={advisor.send}
          onToggleMic={() => setMicMuted(!isMicMuted)}
        />
        {/*
          Snap sheets are full-height layers translated down by the snap
          offset: only the top `snap` fraction is visible. This spacer keeps
          the composer pinned to the visible bottom edge at every snap (it
          collapses to zero at full screen).
        */}
        <div aria-hidden="true" className="shrink-0" style={{ height: `${(1 - visibleFraction) * 100}%` }} />
      </SnapSheet>
    </>
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
        <div className="relative h-dvh w-full overflow-hidden bg-surface-sub sm:my-auto sm:h-[min(853px,calc(100dvh-3rem))] sm:max-w-md sm:rounded-lg sm:border sm:border-outline">
          {sessionToken ? (
            <SessionPanel
              key={sessionToken}
              sessionToken={sessionToken}
              voiceEnabled={voiceEnabled}
              micUnavailable={micUnavailable}
              onEnded={handleEnded}
              registerCommands={registerCommands}
              onEvent={handlePanelEvent}
            />
          ) : (
            <div className="relative flex h-full flex-col items-center justify-center gap-5 p-6 pt-safe pb-safe">
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
          )}
        </div>
      </div>
    </AppShell>
  );
}
