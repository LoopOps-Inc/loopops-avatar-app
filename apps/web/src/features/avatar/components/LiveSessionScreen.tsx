import { useCallback, useRef, useState } from 'react';
import type { AvatarSessionResponse, EmbedCommand } from '@loopops/contracts';
import { AppShell } from '@/components/AppShell';
import { useEmbedBridge } from '@/features/embed/hooks/use-embed-bridge';
import {
  ackFirstTurnDisclosures,
  ackVoiceConsent,
  createAdvisorSession,
  createAvatarSession,
  mintDevToken,
} from '@/services/advisor-service';
import { setDevAuth } from '@/services/dev-auth';
import { useTranslation } from '@/i18n';
import { useInvestors } from '../hooks/use-investors';
import { SessionPanel, type PanelCommands } from './SessionPanel';
import { StartScreen } from './StartScreen';
import { avatarLog } from '../lib/avatar-debug';

type DemoSession = {
  threadId: string;
  threadStartedAt: string;
  avatar: AvatarSessionResponse;
  startedAt: number;
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
  const { investors, selected, select, loading: investorsLoading } = useInvestors();
  const [demoSession, setDemoSession] = useState<DemoSession | null>(null);
  const demoSessionRef = useRef<DemoSession | null>(null);
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [micUnavailable, setMicUnavailable] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [endedByServer, setEndedByServer] = useState(false);
  const commandsRef = useRef<PanelCommands | null>(null);
  const audioUnlockedRef = useRef(false);

  const setSession = useCallback((session: DemoSession | null) => {
    demoSessionRef.current = session;
    setDemoSession(session);
  }, []);

  const handleEnded = useCallback(
    (reason: 'user' | 'server' | 'error') => {
      const current = demoSessionRef.current;
      if (reason === 'server' && current) {
        const elapsedS = (Date.now() - current.startedAt) / 1000;
        if (elapsedS >= current.avatar.max_session_duration_s - 10) {
          avatarLog('session.renew', { elapsed_s: elapsedS });
          void (async () => {
            try {
              const avatar = await createAvatarSession(current.threadId, 'portrait');
              setSession({
                threadId: current.threadId,
                threadStartedAt: current.threadStartedAt,
                avatar,
                startedAt: Date.now(),
              });
            } catch {
              audioUnlockedRef.current = false;
              setSession(null);
              setEndedByServer(true);
            }
          })();
          return;
        }
      }
      audioUnlockedRef.current = false;
      setSession(null);
      setEndedByServer(reason === 'server');
    },
    [setSession],
  );

  const handleStart = useCallback(() => {
    audioUnlockedRef.current = true;
    avatarLog('session.start', { audioUnlocked: true });
    void (async () => {
      setStarting(true);
      setError(null);
      setEndedByServer(false);
      const micAvailable = await probeMic();
      setMicUnavailable(!micAvailable);
      try {
        if (selected) {
          const token = await mintDevToken(String(selected.numero_cliente_unico));
          setDevAuth({
            clientId: token.client_id,
            accessToken: token.access_token,
            expiresAt: Date.now() + token.expires_in * 1000,
          });
        }
        const advisorSession = await createAdvisorSession();
        await ackFirstTurnDisclosures();
        await ackVoiceConsent();
        const avatar = await createAvatarSession(advisorSession.thread_id, 'portrait');
        setVoiceEnabled(micAvailable);
        setSession({
          threadId: advisorSession.thread_id,
          threadStartedAt: advisorSession.thread_started_at,
          avatar,
          startedAt: Date.now(),
        });
      } catch (err) {
        setError(err instanceof Error && err.message ? err.message : t('live.error_unknown'));
      } finally {
        setStarting(false);
      }
    })();
  }, [t, selected, setSession]);

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
              key={demoSession.threadId}
              threadId={demoSession.threadId}
              threadStartedAt={demoSession.threadStartedAt}
              avatarSession={demoSession.avatar}
              voiceEnabled={voiceEnabled}
              micUnavailable={micUnavailable}
              audioUnlockedRef={audioUnlockedRef}
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
              investors={investors}
              selectedInvestorId={selected?.numero_cliente_unico ?? null}
              onSelectInvestor={select}
              investorsLoading={investorsLoading}
            />
          )}
        </div>
      </div>
    </AppShell>
  );
}
