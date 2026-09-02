import { useCallback, useEffect, useRef, useState } from 'react';
import type { RefObject } from 'react';
import type { UIComponent } from '@loopops/contracts';
import { UIComponentSchema } from '@loopops/contracts';
import {
  ConnectionQuality,
  Room,
  RoomEvent,
  type RemoteTrack,
  type RemoteVideoTrack,
} from 'livekit-client';
import { appEnv } from '@/config/env';
import { avatarLog } from '@/features/avatar/lib/avatar-debug';

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

export function buildAudioWsUrl(audioWsPath: string): string {
  const base = appEnv.advisorApiBase;
  if (/^https?:\/\//i.test(base)) {
    return `${base.replace(/\/$/, '').replace(/^http/i, 'ws')}${audioWsPath}`;
  }
  const prefix = base.startsWith('/') ? base.replace(/\/$/, '') : `/${base.replace(/\/$/, '')}`;
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${window.location.host}${prefix}${audioWsPath}`;
}

function pickRecorderMime(): string {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm'];
  for (const mime of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(mime)) return mime;
  }
  return '';
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

  const tryStartPlayback = useCallback(
    async (unmute = false) => {
      if (audioUnlockedRef && !audioUnlockedRef.current) {
        avatarLog('playback.skipped', { reason: 'not_unlocked', unmute });
        return;
      }

      const video = videoRef.current;
      if (video) {
        if (unmute) video.muted = false;
        try {
          await video.play();
          avatarLog('playback.video', { unmute, paused: video.paused, muted: video.muted });
        } catch (err) {
          avatarLog('playback.video_failed', {
            unmute,
            error: err instanceof Error ? err.name : 'unknown',
          });
        }
      }

      const audio = audioElementRef.current;
      if (audio) {
        try {
          await audio.play();
          avatarLog('playback.audio', { paused: audio.paused });
        } catch (err) {
          avatarLog('playback.audio_failed', {
            error: err instanceof Error ? err.name : 'unknown',
          });
        }
      } else {
        avatarLog('playback.no_audio_element', { unmute });
      }
    },
    [audioUnlockedRef, videoRef],
  );

  const sendJson = useCallback((frame: Record<string, unknown>) => {
    const socket = socketRef.current;
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify(frame));
    }
  }, []);

  const maybeSendReady = useCallback(() => {
    const tracks = tracksReadyRef.current;
    // HeyGen LITE muxes speech into the video track; a separate audio track is optional.
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
    tracks.readySent = true;
    sendJson({
      type: 'client.ready',
      has_video: tracks.video,
      has_audio: tracks.audio,
    });
    avatarLog('client.ready.sent', { has_audio_track: tracks.audio });
    void tryStartPlayback(true);
  }, [sendJson, tryStartPlayback]);

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
    if (!videoTrackRef.current || !videoRef.current) return;
    const element = videoRef.current;
    videoTrackRef.current.attach(element);
    return () => {
      videoTrackRef.current?.detach(element);
    };
  }, [videoRef, status]);

  useEffect(() => {
    userStoppedRef.current = false;
    let disposed = false;
    let audioElement: HTMLMediaElement | null = null;
    const room = new Room({ adaptiveStream: true, dynacast: true });
    const socket = new WebSocket(buildAudioWsUrl(audioWsPath));
    socketRef.current = socket;
    avatarLog('ws.connecting', { path: audioWsPath });

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
          void tryStartPlayback(true);
          break;
        case 'caption':
          handlersRef.current.onCaption(text);
          void tryStartPlayback(true);
          break;
        case 'ui': {
          const parsed = UIComponentSchema.safeParse(frame);
          if (parsed.success) handlersRef.current.onUi(parsed.data);
          break;
        }
        case 'turn.complete':
          handlersRef.current.onTurnComplete();
          break;
        default:
          break;
      }
    };

    socket.onclose = () => {
      avatarLog('ws.closed', { userStopped: userStoppedRef.current });
      if (!disposed && !userStoppedRef.current) {
        handlersRef.current.onClosed();
      }
    };

    const handleVisibility = () => {
      sendJson({ type: document.hidden ? 'client.background' : 'client.foreground' });
    };
    document.addEventListener('visibilitychange', handleVisibility);

    room
      .on(RoomEvent.Connected, () => {
        if (!disposed) {
          avatarLog('livekit.connected');
          setStatus('connected');
          void tryStartPlayback(true);
        }
      })
      .on(RoomEvent.Reconnecting, () => {
        if (!disposed) setStatus('reconnecting');
      })
      .on(RoomEvent.Reconnected, () => {
        if (!disposed) setStatus('connected');
      })
      .on(RoomEvent.ConnectionQualityChanged, (quality: ConnectionQuality) => {
        if (!disposed) setConnectionQuality(quality);
      })
      .on(RoomEvent.Disconnected, () => {
        if (disposed) return;
        setStatus('disconnected');
        if (!userStoppedRef.current) handlersRef.current.onClosed();
      })
      .on(RoomEvent.TrackSubscribed, (track: RemoteTrack) => {
        if (track.kind === 'video') {
          avatarLog('livekit.video_track');
          videoTrackRef.current = track as RemoteVideoTrack;
          tracksReadyRef.current.video = true;
          const element = videoRef.current;
          if (element) {
            element.muted = true;
            element.defaultMuted = true;
            (track as RemoteVideoTrack).attach(element);
            void tryStartPlayback(false);
          }
          maybeSendReady();
        } else if (track.kind === 'audio') {
          avatarLog('livekit.audio_track');
          tracksReadyRef.current.audio = true;
          const element = track.attach();
          element.autoplay = true;
          element.style.display = 'none';
          document.body.appendChild(element);
          audioElement = element;
          audioElementRef.current = element;
          void tryStartPlayback(false);
          maybeSendReady();
        }
      });

    void (async () => {
      try {
        await room.connect(livekitUrl, livekitToken);
        if (disposed) {
          userStoppedRef.current = true;
          await room.disconnect();
          return;
        }
        setStatus('connected');
      } catch {
        if (!disposed) {
          avatarLog('livekit.connect_failed');
          setStatus('failed');
        }
      }
    })();

    const videoElement = videoRef.current;
    return () => {
      disposed = true;
      userStoppedRef.current = true;
      tracksReadyRef.current = { video: false, audio: false, readySent: false };
      document.removeEventListener('visibilitychange', handleVisibility);
      const recorder = recorderRef.current;
      if (recorder && recorder.state !== 'inactive') recorder.stop();
      recorderRef.current = null;
      micStreamRef.current?.getTracks().forEach((track) => track.stop());
      micStreamRef.current = null;
      socket.onclose = null;
      socket.close();
      socketRef.current = null;
      if (videoTrackRef.current && videoElement) {
        videoTrackRef.current.detach(videoElement);
      }
      videoTrackRef.current = null;
      audioElement?.pause();
      audioElement?.remove();
      audioElementRef.current = null;
      void room.disconnect();
      setStatus('disconnected');
    };
  }, [
    livekitUrl,
    livekitToken,
    audioWsPath,
    videoRef,
    sendJson,
    flushSpeakQueue,
    tryStartPlayback,
    maybeSendReady,
  ]);

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
