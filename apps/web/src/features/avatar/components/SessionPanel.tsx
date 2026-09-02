import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { UIComponent } from '@loopops/contracts';
import type { AvatarSessionResponse } from '@loopops/contracts';
import { Loader2 } from 'lucide-react';
import type { EmbedEvent } from '@loopops/contracts';
import { useAdvisorChat } from '../hooks/use-advisor-chat';
import { useTranslation } from '@/i18n';
import { formatChatStartedAt } from '../lib/format-chat-day';
import { sessionStateClass, sessionStateLabel } from '../lib/session-status';
import { useLiveAvatarSession } from '../hooks/use-liveavatar-session';
import { createAgentAdvisorService } from '../services/agent-advisor-service';
import { avatarLog } from '../lib/avatar-debug';
import { ChatArea } from './ChatArea';
import { SessionRail } from './SessionRail';
import { SnapSheet } from './SnapSheet';

export type PanelCommands = {
  stop: () => void;
  setMicMuted: (muted: boolean) => void;
};

type SessionPanelProps = {
  threadId: string;
  threadStartedAt: string;
  avatarSession: AvatarSessionResponse;
  voiceEnabled: boolean;
  micUnavailable: boolean;
  audioUnlockedRef: React.RefObject<boolean>;
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
 * collapses at the full-screen snap (future forms/firma). The advisor
 * service owns the transcript; the avatar never speaks first — the backend
 * only speaks in reply, via the audio WebSocket (voice turns and chat
 * replies through client.speak).
 */
export function SessionPanel({
  threadId,
  threadStartedAt,
  avatarSession,
  voiceEnabled,
  micUnavailable,
  audioUnlockedRef,
  onEnded,
  registerCommands,
  onEvent,
}: SessionPanelProps) {
  const { t, locale } = useTranslation();
  const voiceAdvisorRef = useRef<{
    appendUserMessage: (text: string) => void;
    appendCaption: (text: string) => void;
    appendUi: (component: UIComponent) => void;
  } | null>(null);
  const captionBufferRef = useRef<string[]>([]);

  const session = useLiveAvatarSession(avatarSession, {
    voiceChat: voiceEnabled,
    audioUnlockedRef,
    onTranscriptFinal: (text) => voiceAdvisorRef.current?.appendUserMessage(text),
    onCaption: (text) => {
      if (voiceAdvisorRef.current) {
        avatarLog('caption.append', { chars: text.length });
        voiceAdvisorRef.current.appendCaption(text);
        return;
      }
      avatarLog('caption.buffered', { chars: text.length });
      captionBufferRef.current.push(text);
    },
    onUi: (component) => voiceAdvisorRef.current?.appendUi(component),
  });
  const [snapIndex, setSnapIndex] = useState(LOADING_SNAP);

  const {
    sessionState,
    isStreamReady,
    connectionQuality,
    isAvatarTalking,
    isUserTalking,
    isMicMuted,
    micError,
    endReason,
    videoRef,
    stop,
    attach,
    interrupt,
    setMicMuted,
    speak,
    unlockPlayback,
  } = session;

  const isConnected = sessionState === 'CONNECTED';
  const service = useMemo(() => createAgentAdvisorService(threadId), [threadId]);
  const advisor = useAdvisorChat({ speak, service });

  const sendMessage = useCallback(
    (message: string) => {
      void unlockPlayback(true);
      advisor.send(message);
    },
    [advisor, unlockPlayback],
  );

  useEffect(() => {
    voiceAdvisorRef.current = {
      appendUserMessage: advisor.appendUserMessage,
      appendCaption: advisor.appendCaption,
      appendUi: advisor.appendUi,
    };
    for (const text of captionBufferRef.current) {
      avatarLog('caption.flush', { chars: text.length });
      advisor.appendCaption(text);
    }
    captionBufferRef.current = [];
  });

  useEffect(() => {
    registerCommands({ stop: () => void stop(), setMicMuted });
    return () => registerCommands(null);
  }, [registerCommands, stop, setMicMuted]);

  useEffect(() => {
    if (isStreamReady && videoRef.current) {
      attach(videoRef.current);
    }
  }, [isStreamReady, attach, videoRef]);

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

  const endedKeyRef = useRef<string | null>(null);
  useEffect(() => {
    if (!endReason) return;
    const key = `${avatarSession.avatar_session_id}:${endReason}`;
    if (endedKeyRef.current === key) return;
    endedKeyRef.current = key;
    onEvent({ type: 'ended', payload: { reason: endReason } });
    onEnded(endReason);
  }, [endReason, onEvent, avatarSession.avatar_session_id, onEnded]);

  const isPoorQuality = connectionQuality === 'BAD';
  const chatDayLabel = formatChatStartedAt(new Date(threadStartedAt).getTime(), locale);
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
      headerLabel={chatDayLabel}
      above={
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
        micUnavailable={micUnavailable || micError}
        onSend={sendMessage}
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
