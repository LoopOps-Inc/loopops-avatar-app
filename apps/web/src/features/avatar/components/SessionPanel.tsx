import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { ConnectionQuality, SessionState } from '@heygen/liveavatar-web-sdk';
import type { EmbedEvent } from '@loopops/contracts';
import { actinverAvatar } from '@/config/avatar';
import { useAdvisorChat } from '../hooks/use-advisor-chat';
import { useTranslation } from '@/i18n';
import { sessionStateClass, sessionStateLabel } from '../lib/session-status';
import { useLiveAvatarSession } from '../hooks/use-liveavatar-session';
import { ChatArea } from './ChatArea';
import { SessionRail } from './SessionRail';
import { SnapSheet } from './SnapSheet';

export type PanelCommands = {
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

/**
 * The avatar video is the base layer; the chat lives in a bottom snap sheet
 * (Motion) docked over it. Snap points control how much of the frame the
 * sheet occupies — the video layer resizes to the space left free and
 * collapses at the full-screen snap (future forms/firma). The advisor mock
 * owns the transcript; the avatar only speaks what the advisor sends, so
 * HeyGen transcriptions are not rendered.
 */
export function SessionPanel({
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
    isPreview,
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

  return (
    <SnapSheet
      snaps={SNAP_POINTS}
      activeIndex={effectiveSnap}
      onActiveIndexChange={setSnapIndex}
      label={t('live.title')}
      above={
        <>
          {isPreview ? (
            <img
              src={actinverAvatar.previewImageUrl}
              alt=""
              className="h-full w-full object-cover"
            />
          ) : (
            <>
              <video ref={videoRef} autoPlay playsInline className="h-full w-full object-cover" />
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
          )}
        </>
      }
    >
      <SessionRail
        stateText={sessionStateLabel(sessionState, t)}
        stateClass={sessionStateClass(sessionState)}
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
      <div
        aria-hidden="true"
        className="shrink-0"
        style={{ height: `${(1 - visibleFraction) * 100}%` }}
      />
    </SnapSheet>
  );
}
