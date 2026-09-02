import { useCallback, useRef, useState } from 'react';
import type { AvatarSessionResponse, EmbedCommand } from '@loopops/contracts';
import { AppShell } from '@/components/AppShell';
import { useEmbedBridge } from '@/features/embed/hooks/use-embed-bridge';
import {
  ackFirstTurnDisclosures,
  ackVoiceConsent,
  createAdvisorSession,
  createAvatarSession,
} from '@/services/advisor-service';
import { useTranslation } from '@/i18n';
import { SessionPanel, type PanelCommands } from './SessionPanel';
import { StartScreen } from './StartScreen';

type DemoSession = {
  threadId: string;
  avatar: AvatarSessionResponse;
};

async function probeMic(): Promise<boolean> {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    stream.getTracks().forEach((track) => track.stop());
    return true;
  } catch {
    return false;
  }
}

/**
 * Route shell: owns the session lifecycle (mic probe, advisor thread, avatar
 * session credentials, embed bridge) and swaps between the start hero and
 * the live session panel inside the phone frame.
 */
export function LiveSessionRoute() {
  const { t } = useTranslation();
  const [demoSession, setDemoSession] = useState<DemoSession | null>(null);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [micUnavailable, setMicUnavailable] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [endedByServer, setEndedByServer] = useState(false);
  const commandsRef = useRef<PanelCommands | null>(null);

  const handleEnded = useCallback((reason: 'user' | 'server' | 'error') => {
    setDemoSession(null);
    setEndedByServer(reason === 'server');
  }, []);

  const handleStart = useCallback(async () => {
    setStarting(true);
    setError(null);
    setEndedByServer(false);
    const micAvailable = await probeMic();
    setMicUnavailable(!micAvailable);
    try {
      const advisorSession = await createAdvisorSession();
      await ackFirstTurnDisclosures();
      await ackVoiceConsent();
      const avatar = await createAvatarSession(advisorSession.thread_id, 'portrait');
      setVoiceEnabled(micAvailable);
      setDemoSession({ threadId: advisorSession.thread_id, avatar });
    } catch (err) {
      setError(
        err instanceof Error && err.message ? err.message : t('live.error_unknown'),
      );
    } finally {
      setStarting(false);
    }
  }, [t]);

  const handleCommand = useCallback(
    (command: EmbedCommand) => {
      switch (command.type) {
        case 'start':
          if (!demoSession) void handleStart();
          break;
        case 'stop':
          commandsRef.current?.stop();
          break;
        case 'setMuted':
          commandsRef.current?.setMicMuted(command.payload.muted);
          break;
      }
    },
    [handleStart, demoSession],
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
      <div className="bg-surface-sub flex min-h-dvh justify-center">
        <div className="bg-surface-sub sm:border-outline relative h-dvh w-full overflow-hidden sm:my-auto sm:h-[min(853px,calc(100dvh-3rem))] sm:max-w-md sm:rounded-lg sm:border">
          {demoSession ? (
            <SessionPanel
              key={demoSession.avatar.avatar_session_id}
              threadId={demoSession.threadId}
              avatarSession={demoSession.avatar}
              voiceEnabled={voiceEnabled}
              micUnavailable={micUnavailable}
              onEnded={handleEnded}
              registerCommands={registerCommands}
              onEvent={handlePanelEvent}
            />
          ) : (
            <StartScreen
              starting={starting}
              error={error}
              endedByServer={endedByServer}
              onStart={() => void handleStart()}
            />
          )}
        </div>
      </div>
    </AppShell>
  );
}
