import { useCallback, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import type { UIComponent } from '@loopops/contracts';
import {
  SseCitationsEventSchema,
  SseErrorEventSchema,
  SseFormSpecEventSchema,
  UIComponentSchema,
} from '@loopops/contracts';
import {
  ConnectionQuality,
  Room,
  RoomEvent,
  type RemoteTrack,
  type RemoteVideoTrack,
} from 'livekit-client';
import { appEnv } from '@/config/env';
import { avatarLog } from '@/features/avatar/lib/avatar-debug';
import { getDevAuth } from '@/services/dev-auth';

export type AvatarConnectionStatus =
  'connecting' | 'connected' | 'reconnecting' | 'disconnected' | 'failed';

type LivekitAvatarHandlers = {
  onTranscriptPartial: (text: string) => void;
  onTranscriptFinal: (text: string) => void;
  onThinking: () => void;
  onFiller: (text: string) => void;
  onAgentSpeaking: () => void;
  onCaption: (text: string) => void;
  onUi: (component: UIComponent) => void;
  onTurnComplete: () => void;
  onClosed: () => void;
};

type LivekitAvatarSessionOptions = {
  livekitUrl: string;
  livekitToken: string;
  audioWsPath: string;
  videoRef: RefObject<HTMLVideoElement | null>;
  handlers: LivekitAvatarHandlers;
  /** Set synchronously inside the start-session click handler so playback can unlock. */
  audioUnlockedRef?: RefObject<boolean>;
};

export function buildAudioWsUrl(
  audioWsPath: string,
  accessToken: string | null | undefined = getDevAuth()?.accessToken,
): string {
  const base = appEnv.advisorApiBase;
  let url: string;
  if (/^https?:\/\//i.test(base)) {
    url = `${base.replace(/\/$/, '').replace(/^http/i, 'ws')}${audioWsPath}`;
  } else {
    const prefix = base.startsWith('/') ? base.replace(/\/$/, '') : `/${base.replace(/\/$/, '')}`;
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    url = `${protocol}://${window.location.host}${prefix}${audioWsPath}`;
  }
  if (!accessToken) return url;
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}access_token=${encodeURIComponent(accessToken)}`;
}

function pickRecorderMime(): string {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm'];
  for (const mime of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(mime)) return mime;
  }
  return '';
}

/** Survive React StrictMode's effect connect → cleanup → connect cycle. */
const STRICT_TEARDOWN_MS = 150;

function prepareVideoElement(video: HTMLVideoElement, unlocked: boolean): void {
  video.playsInline = true;
  video.autoplay = true;
  video.muted = !unlocked;
  video.defaultMuted = !unlocked;
}

/**
 * Extract the component from a voice-socket `ui` frame.
 *
 * The wire format is `{"type":"ui","component":{...UIComponent}}` (ws_handler.py).
 * Parsing the frame itself used to "succeed": the envelope satisfied the
 * permissive variant of UIComponentSchema, so every voice turn delivered a
 * component of type `"ui"` and no card ever rendered.
 */
export function parseUiFrame(frame: Record<string, unknown>): UIComponent | null {
  const parsed = UIComponentSchema.safeParse(frame.component);
  return parsed.success ? parsed.data : null;
}

/**
 * Normalise every renderable voice frame into a `UIComponent`.
 *
 * Only `ui` nests its component; `citations`, `form_spec` and `error` are
 * spread flat into the frame (voice/pipeline.py: `{"type": kind, **event.data}`).
 * All of them already have a card, so routing them through the same handler
 * needs no plumbing of its own. An `error` becomes a warning banner because its
 * `message` is a client-facing Spanish sentence meant to be shown; it is also
 * spoken as a caption, so dropping it left the user hearing something with
 * nothing on screen.
 */
export function frameToComponent(frame: Record<string, unknown>): UIComponent | null {
  switch (frame.type) {
    case 'ui':
      return parseUiFrame(frame);
    case 'citations': {
      const parsed = SseCitationsEventSchema.safeParse(frame);
      return parsed.success ? { type: 'citations', payload: parsed.data } : null;
    }
    case 'form_spec': {
      const parsed = SseFormSpecEventSchema.safeParse(frame);
      if (!parsed.success) return null;
      const payload = { ...parsed.data };
      delete payload.type;
      return { type: 'form_spec', payload } as UIComponent;
    }
    case 'error': {
      const parsed = SseErrorEventSchema.safeParse(frame);
      return parsed.success
        ? {
            type: 'warning_banner',
            payload: { severity: 'warning', message: parsed.data.message },
          }
        : null;
    }
    default:
      return null;
  }
}

export function useLivekitAvatarSession({
  livekitUrl,
  livekitToken,
  audioWsPath,
  videoRef,
  handlers,
  audioUnlockedRef,
}: LivekitAvatarSessionOptions) {
  const [status, setStatus] = useState<AvatarConnectionStatus>('connecting');
  const [connectionQuality, setConnectionQuality] = useState<ConnectionQuality>(
    ConnectionQuality.Unknown,
  );
  const [micActive, setMicActive] = useState(false);
  const [micError, setMicError] = useState(false);
  const [roomCreds, setRoomCreds] = useState({ url: livekitUrl, token: livekitToken });
  const [prevPropCredsKey, setPrevPropCredsKey] = useState(`${livekitUrl}\0${livekitToken}`);
  const propCredsKey = `${livekitUrl}\0${livekitToken}`;
  if (propCredsKey !== prevPropCredsKey) {
    setPrevPropCredsKey(propCredsKey);
    setRoomCreds({ url: livekitUrl, token: livekitToken });
  }

  const handlersRef = useRef(handlers);
  useEffect(() => {
    handlersRef.current = handlers;
  }, [handlers]);

  const socketRef = useRef<WebSocket | null>(null);
  const speakQueueRef = useRef<string[]>([]);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);
  const userStoppedRef = useRef(false);
  const videoTrackRef = useRef<RemoteVideoTrack | null>(null);
  const audioElementRef = useRef<HTMLMediaElement | null>(null);
  const tracksReadyRef = useRef({ video: false, audio: false, readySent: false });
  const playGenRef = useRef(0);
  const wsHoldRef = useRef<{
    socket: WebSocket;
    path: string;
    onVisibility: () => void;
  } | null>(null);
  const wsTimerRef = useRef(0);
  const liveHoldRef = useRef<{
    room: Room;
    key: string;
    audioEl: HTMLMediaElement | null;
  } | null>(null);
  const liveTimerRef = useRef(0);

  const tryStartPlayback = useCallback(
    async (unmute = false): Promise<boolean> => {
      if (audioUnlockedRef && !audioUnlockedRef.current) {
        avatarLog('playback.skipped', { reason: 'not_unlocked', unmute });
        return false;
      }

      const gen = ++playGenRef.current;
      const playMedia = async (media: HTMLMediaElement, kind: 'video' | 'audio') => {
        try {
          await media.play();
          if (gen !== playGenRef.current) return false;
          avatarLog(`playback.${kind}`, {
            unmute,
            paused: media.paused,
            muted: media.muted,
          });
          return !media.paused;
        } catch (err) {
          if (gen !== playGenRef.current) return false;
          const error = err instanceof Error ? err.name : 'unknown';
          avatarLog(`playback.${kind}_failed`, { unmute, error });
          if (error !== 'AbortError') return false;
          await new Promise((resolve) => window.setTimeout(resolve, 80));
          if (gen !== playGenRef.current) return false;
          try {
            await media.play();
            avatarLog(`playback.${kind}_retry`, { paused: media.paused, muted: media.muted });
            return !media.paused;
          } catch (retryErr) {
            avatarLog(`playback.${kind}_failed`, {
              unmute,
              error: retryErr instanceof Error ? retryErr.name : 'unknown',
              retry: true,
            });
            return false;
          }
        }
      };

      const video = videoRef.current;
      let videoOk = true;
      if (video) {
        prepareVideoElement(video, true);
        if (unmute) {
          video.muted = false;
          video.defaultMuted = false;
        }
        videoOk = await playMedia(video, 'video');
      }

      const audio = audioElementRef.current;
      if (audio) {
        audio.muted = false;
        await playMedia(audio, 'audio');
      } else {
        avatarLog('playback.no_audio_element', { unmute });
      }
      return videoOk;
    },
    [audioUnlockedRef, videoRef],
  );

  const sendJson = useCallback((frame: Record<string, unknown>) => {
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(frame));
    }
  }, []);

  const readyRetryRef = useRef(0);
  const maybeSendReadyRef = useRef<() => void>(() => {});
  const maybeSendReady = useCallback(() => {
    void (async () => {
      const tracks = tracksReadyRef.current;
      if (tracks.readySent || !tracks.video) {
        avatarLog('client.ready.waiting', {
          video: tracks.video,
          audio: tracks.audio,
          sent: tracks.readySent,
          ws: socketRef.current?.readyState,
        });
        return;
      }
      const socket = socketRef.current;
      if (!socket || socket.readyState !== WebSocket.OPEN) return;
      const playing = await tryStartPlayback(true);
      if (tracks.readySent) return;
      if (!playing) {
        if (readyRetryRef.current >= 5) return;
        readyRetryRef.current += 1;
        window.setTimeout(() => maybeSendReadyRef.current(), 160);
        return;
      }
      tracks.readySent = true;
      sendJson({
        type: 'client.ready',
        has_video: tracks.video,
        has_audio: tracks.audio,
      });
      avatarLog('client.ready.sent', { has_audio_track: tracks.audio });
    })();
  }, [sendJson, tryStartPlayback]);

  useEffect(() => {
    maybeSendReadyRef.current = maybeSendReady;
  }, [maybeSendReady]);

  const flushSpeakQueue = useCallback(() => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return;
    for (const text of speakQueueRef.current) {
      socket.send(JSON.stringify({ type: 'client.speak', text }));
    }
    speakQueueRef.current = [];
  }, []);

  const sendSpeak = useCallback(
    (text: string) => {
      const trimmed = text.trim();
      if (!trimmed) return;
      const socket = socketRef.current;
      if (socket?.readyState === WebSocket.OPEN) {
        avatarLog('client.speak.sent', { chars: trimmed.length });
        sendJson({ type: 'client.speak', text: trimmed });
        return;
      }
      avatarLog('client.speak.queued', { chars: trimmed.length, ws: socket?.readyState });
      speakQueueRef.current.push(trimmed);
    },
    [sendJson],
  );

  const stopMic = useCallback(() => {
    const recorder = recorderRef.current;
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop();
    }
    micStreamRef.current?.getTracks().forEach((track) => track.stop());
    micStreamRef.current = null;
    recorderRef.current = null;
    setMicActive(false);
  }, []);

  const startMic = useCallback(async () => {
    if (recorderRef.current || micActive) return;
    setMicError(false);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mime = pickRecorderMime();
      const recorder = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
      micStreamRef.current = stream;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          socketRef.current?.send(event.data);
        }
      };
      recorder.onstop = () => {
        sendJson({ type: 'utterance_end' });
        stream.getTracks().forEach((track) => track.stop());
        if (micStreamRef.current === stream) micStreamRef.current = null;
        if (recorderRef.current === recorder) recorderRef.current = null;
        setMicActive(false);
      };
      recorderRef.current = recorder;
      recorder.start(250);
      sendJson({ type: 'audio_start', mime: mime || 'audio/webm' });
      setMicActive(true);
    } catch {
      micStreamRef.current = null;
      setMicError(true);
      setMicActive(false);
    }
  }, [micActive, sendJson]);

  const sendBargeIn = useCallback(() => {
    stopMic();
    sendJson({ type: 'client.barge_in' });
  }, [sendJson, stopMic]);

  const sendKeepAlive = useCallback(() => {
    sendJson({ type: 'client.foreground' });
  }, [sendJson]);

  useEffect(() => {
    window.clearTimeout(wsTimerRef.current);
    const hold = wsHoldRef.current;
    const reusable =
      hold &&
      hold.path === audioWsPath &&
      hold.socket.readyState !== WebSocket.CLOSING &&
      hold.socket.readyState !== WebSocket.CLOSED;

    if (reusable && hold) {
      socketRef.current = hold.socket;
      userStoppedRef.current = false;
      return () => {
        wsTimerRef.current = window.setTimeout(() => {
          if (wsHoldRef.current !== hold) return;
          userStoppedRef.current = true;
          document.removeEventListener('visibilitychange', hold.onVisibility);
          hold.socket.onclose = null;
          hold.socket.close();
          if (socketRef.current === hold.socket) socketRef.current = null;
          wsHoldRef.current = null;
        }, STRICT_TEARDOWN_MS);
      };
    }

    if (hold) {
      userStoppedRef.current = true;
      document.removeEventListener('visibilitychange', hold.onVisibility);
      hold.socket.onclose = null;
      hold.socket.close();
      if (socketRef.current === hold.socket) socketRef.current = null;
      wsHoldRef.current = null;
    }

    userStoppedRef.current = false;
    tracksReadyRef.current.readySent = false;
    readyRetryRef.current = 0;
    const socket = new WebSocket(buildAudioWsUrl(audioWsPath));
    socketRef.current = socket;
    avatarLog('ws.connecting', { path: audioWsPath });

    const handleVisibility = () => {
      sendJson({ type: document.hidden ? 'client.background' : 'client.foreground' });
    };
    const next = { socket, path: audioWsPath, onVisibility: handleVisibility };
    wsHoldRef.current = next;

    socket.onopen = () => {
      avatarLog('ws.open');
      flushSpeakQueue();
      maybeSendReady();
    };

    socket.onmessage = (event: MessageEvent) => {
      if (typeof event.data !== 'string') return;
      let frame: Record<string, unknown>;
      try {
        frame = JSON.parse(event.data) as Record<string, unknown>;
      } catch {
        return;
      }
      const text = typeof frame.text === 'string' ? frame.text : '';
      const frameType = typeof frame.type === 'string' ? frame.type : 'unknown';
      avatarLog('ws.message', { type: frameType, textLen: text.length });
      switch (frame.type) {
        case 'transcript.partial':
          handlersRef.current.onTranscriptPartial(text);
          break;
        case 'transcript.final':
          handlersRef.current.onTranscriptFinal(text);
          break;
        case 'agent.thinking':
          handlersRef.current.onThinking();
          break;
        case 'filler':
          handlersRef.current.onFiller(text);
          break;
        case 'agent.speaking':
          handlersRef.current.onAgentSpeaking();
          if (videoRef.current?.paused) void tryStartPlayback(true);
          break;
        case 'caption':
          handlersRef.current.onCaption(text);
          if (videoRef.current?.paused) void tryStartPlayback(true);
          break;
        case 'ui':
        case 'citations':
        case 'form_spec':
        case 'error': {
          const component = frameToComponent(frame);
          if (component) handlersRef.current.onUi(component);
          break;
        }
        case 'turn.complete':
          handlersRef.current.onTurnComplete();
          break;
        case 'session.refreshed': {
          const nextUrl = typeof frame.livekit_url === 'string' ? frame.livekit_url : '';
          const nextToken =
            typeof frame.livekit_client_token === 'string' ? frame.livekit_client_token : '';
          if (nextUrl && nextToken) {
            avatarLog('session.refreshed', { urlHost: nextUrl.slice(0, 48) });
            setRoomCreds({ url: nextUrl, token: nextToken });
          }
          break;
        }
        default:
          break;
      }
    };

    socket.onclose = () => {
      avatarLog('ws.closed', { userStopped: userStoppedRef.current });
      if (wsHoldRef.current === next) wsHoldRef.current = null;
      if (!userStoppedRef.current) {
        handlersRef.current.onClosed();
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      wsTimerRef.current = window.setTimeout(() => {
        if (wsHoldRef.current !== next) return;
        userStoppedRef.current = true;
        document.removeEventListener('visibilitychange', handleVisibility);
        const recorder = recorderRef.current;
        if (recorder && recorder.state !== 'inactive') recorder.stop();
        recorderRef.current = null;
        micStreamRef.current?.getTracks().forEach((track) => track.stop());
        micStreamRef.current = null;
        socket.onclose = null;
        socket.close();
        if (socketRef.current === socket) socketRef.current = null;
        wsHoldRef.current = null;
      }, STRICT_TEARDOWN_MS);
    };
  }, [audioWsPath, sendJson, flushSpeakQueue, tryStartPlayback, maybeSendReady, videoRef]);

  useEffect(() => {
    window.clearTimeout(liveTimerRef.current);
    const videoElement = videoRef.current;
    const key = `${roomCreds.url}\0${roomCreds.token}`;
    const hold = liveHoldRef.current;
    if (hold && hold.key === key) {
      return () => {
        liveTimerRef.current = window.setTimeout(() => {
          if (liveHoldRef.current !== hold) return;
          if (videoTrackRef.current && videoElement) {
            videoTrackRef.current.detach(videoElement);
          }
          videoTrackRef.current = null;
          hold.audioEl?.pause();
          hold.audioEl?.remove();
          audioElementRef.current = null;
          void hold.room.disconnect();
          liveHoldRef.current = null;
        }, STRICT_TEARDOWN_MS);
      };
    }

    if (hold) {
      hold.audioEl?.pause();
      hold.audioEl?.remove();
      void hold.room.disconnect();
      liveHoldRef.current = null;
      audioElementRef.current = null;
    }

    if (!roomCreds.url || !roomCreds.token) return;

    const room = new Room({ adaptiveStream: true, dynacast: true });
    const next: { room: Room; key: string; audioEl: HTMLMediaElement | null } = {
      room,
      key,
      audioEl: null,
    };
    liveHoldRef.current = next;
    tracksReadyRef.current.video = false;
    tracksReadyRef.current.audio = false;
    avatarLog('livekit.connecting');

    const isCurrent = () => liveHoldRef.current === next;

    room
      .on(RoomEvent.Connected, () => {
        if (!isCurrent()) return;
        avatarLog('livekit.connected');
        setStatus('connected');
        maybeSendReady();
      })
      .on(RoomEvent.Reconnecting, () => {
        if (isCurrent()) setStatus('reconnecting');
      })
      .on(RoomEvent.Reconnected, () => {
        if (isCurrent()) setStatus('connected');
      })
      .on(RoomEvent.ConnectionQualityChanged, (quality: ConnectionQuality) => {
        if (isCurrent()) setConnectionQuality(quality);
      })
      .on(RoomEvent.Disconnected, () => {
        if (!isCurrent()) return;
        setStatus('disconnected');
        if (!userStoppedRef.current) handlersRef.current.onClosed();
      })
      .on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (!isCurrent()) return;
        if (track.kind === 'video') {
          avatarLog('livekit.video_track');
          videoTrackRef.current = track as RemoteVideoTrack;
          tracksReadyRef.current.video = true;
          const element = videoRef.current;
          if (element) {
            const unlocked = !audioUnlockedRef || Boolean(audioUnlockedRef.current);
            prepareVideoElement(element, unlocked);
            (track as RemoteVideoTrack).attach(element);
          }
          maybeSendReady();
        } else if (track.kind === 'audio') {
          avatarLog('livekit.audio_track');
          tracksReadyRef.current.audio = true;
          const element = track.attach();
          element.autoplay = true;
          element.muted = false;
          element.style.display = 'none';
          document.body.appendChild(element);
          next.audioEl = element;
          audioElementRef.current = element;
          maybeSendReady();
        }
      });

    void (async () => {
      try {
        await room.connect(roomCreds.url, roomCreds.token);
        if (!isCurrent()) {
          await room.disconnect();
          return;
        }
        setStatus('connected');
      } catch {
        if (isCurrent()) {
          avatarLog('livekit.connect_failed');
          setStatus('failed');
        }
      }
    })();

    return () => {
      liveTimerRef.current = window.setTimeout(() => {
        if (liveHoldRef.current !== next) return;
        if (videoTrackRef.current && videoElement) {
          videoTrackRef.current.detach(videoElement);
        }
        videoTrackRef.current = null;
        next.audioEl?.pause();
        next.audioEl?.remove();
        audioElementRef.current = null;
        void room.disconnect();
        liveHoldRef.current = null;
      }, STRICT_TEARDOWN_MS);
    };
  }, [roomCreds.url, roomCreds.token, videoRef, audioUnlockedRef, maybeSendReady]);

  return {
    status,
    isConnected: status === 'connected',
    connectionQuality,
    micActive,
    micError,
    startMic,
    stopMic,
    sendBargeIn,
    sendKeepAlive,
    sendSpeak,
    unlockPlayback: tryStartPlayback,
  };
}
