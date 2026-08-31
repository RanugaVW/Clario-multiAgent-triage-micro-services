'use client';

/**
 * Drives live dictation with automatic engine fallback.
 *
 * Chrome and Edge get the Google-backed Web Speech API. Every other browser -
 * and any Chrome where that service fails to start or dies mid-sentence - is
 * transparently moved onto the faster-whisper microservice over a WebSocket,
 * keeping whatever had already been transcribed.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import {
  BrowserSpeechRecognizer,
  isBrowserSpeechSupported,
} from '../lib/voice/browserSpeech';
import { MicGraph, openMicGraph } from '../lib/voice/micGraph';
import {
  Recognizer,
  RecognizerHandlers,
  TranscriptUpdate,
  VoiceEngine,
  VoiceRecognitionError,
  VoiceStatus,
} from '../lib/voice/types';
import {
  WhisperStreamRecognizer,
  isVoiceServiceReachable,
} from '../lib/voice/whisperStream';

export interface UseVoiceInputOptions {
  /** Called on every partial and final transcript for the whole session. */
  onTranscript: (text: string, isFinal: boolean) => void;
  lang?: string;
}

export interface UseVoiceInputResult {
  isRecording: boolean;
  status: VoiceStatus;
  engine: VoiceEngine | null;
  /** True while a browser-engine failure is being handed to the service. */
  didFallback: boolean;
  error: string | null;
  analyser: AnalyserNode | null;
  start: () => Promise<void>;
  stop: () => Promise<void>;
  toggle: () => Promise<void>;
}

function join(a: string, b: string): string {
  if (!a.trim()) return b;
  if (!b.trim()) return a;
  return `${a.trim()} ${b.trim()}`;
}

export function useVoiceInput({
  onTranscript,
  lang = 'en-US',
}: UseVoiceInputOptions): UseVoiceInputResult {
  const [status, setStatus] = useState<VoiceStatus>('idle');
  const [engine, setEngine] = useState<VoiceEngine | null>(null);
  const [didFallback, setDidFallback] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analyser, setAnalyser] = useState<AnalyserNode | null>(null);

  const graphRef = useRef<MicGraph | null>(null);
  const recognizerRef = useRef<Recognizer | null>(null);
  /** Text finished by engines that already ran in this session. */
  const sessionBaseRef = useRef('');
  /** Latest transcript from the engine currently running. */
  const currentTextRef = useRef('');
  const activeRef = useRef(false);
  const swappingRef = useRef(false);

  const onTranscriptRef = useRef(onTranscript);
  useEffect(() => {
    onTranscriptRef.current = onTranscript;
  }, [onTranscript]);

  const emit = useCallback((update: TranscriptUpdate) => {
    currentTextRef.current = update.transcript;
    onTranscriptRef.current(
      join(sessionBaseRef.current, update.transcript),
      update.isFinal
    );
  }, []);

  const teardown = useCallback(async () => {
    recognizerRef.current = null;
    const graph = graphRef.current;
    graphRef.current = null;
    setAnalyser(null);
    if (graph) await graph.close();
  }, []);

  /** Build a recognizer for `target` wired to the shared update/error path. */
  const makeRecognizer = useCallback(
    (target: VoiceEngine, handlers: RecognizerHandlers): Recognizer =>
      target === 'browser'
        ? new BrowserSpeechRecognizer(handlers, lang)
        : new WhisperStreamRecognizer(handlers),
    [lang]
  );

  // `startEngine` and `handleEngineFailure` call each other; the ref breaks the
  // cycle so neither closure can go stale.
  const failureHandlerRef = useRef<
    (failed: VoiceEngine, err: VoiceRecognitionError) => void
  >(() => undefined);

  const startEngine = useCallback(
    async (target: VoiceEngine, graph: MicGraph) => {
      const handlers: RecognizerHandlers = {
        onUpdate: emit,
        onError: (err) => failureHandlerRef.current(target, err),
      };
      const recognizer = makeRecognizer(target, handlers);
      recognizerRef.current = recognizer;
      currentTextRef.current = '';
      await recognizer.start(graph);
      setEngine(target);
      setStatus('listening');
    },
    [emit, makeRecognizer]
  );

  /** A running engine died: promote whatever it produced and try the service. */
  const handleEngineFailure = useCallback(
    async (failed: VoiceEngine, err: VoiceRecognitionError) => {
      if (!activeRef.current || swappingRef.current) return;

      const graph = graphRef.current;
      const canFallBack =
        failed === 'browser' && err.recoverable && graph !== null;

      if (!canFallBack) {
        activeRef.current = false;
        setError(err.message);
        setStatus('error');
        await teardown();
        return;
      }

      swappingRef.current = true;
      try {
        recognizerRef.current?.abort();
        sessionBaseRef.current = join(
          sessionBaseRef.current,
          currentTextRef.current
        );
        setDidFallback(true);
        setStatus('connecting');
        await startEngine('server', graph!);
        setError(null);
      } catch (fallbackError) {
        activeRef.current = false;
        setError(
          fallbackError instanceof Error
            ? fallbackError.message
            : 'Voice input is unavailable.'
        );
        setStatus('error');
        await teardown();
      } finally {
        swappingRef.current = false;
      }
    },
    [startEngine, teardown]
  );

  useEffect(() => {
    failureHandlerRef.current = (failed, err) => {
      void handleEngineFailure(failed, err);
    };
  }, [handleEngineFailure]);

  const start = useCallback(async () => {
    if (activeRef.current) return;
    activeRef.current = true;
    setError(null);
    setDidFallback(false);
    sessionBaseRef.current = '';
    currentTextRef.current = '';
    setStatus('requesting-mic');

    let graph: MicGraph;
    try {
      graph = await openMicGraph();
    } catch (e) {
      activeRef.current = false;
      setError(
        e instanceof Error ? e.message : 'Could not access the microphone.'
      );
      setStatus('error');
      return;
    }

    graphRef.current = graph;
    setAnalyser(graph.analyser);
    setStatus('connecting');

    const preferred: VoiceEngine = isBrowserSpeechSupported()
      ? 'browser'
      : 'server';

    try {
      await startEngine(preferred, graph);
      return;
    } catch (e) {
      const err =
        e instanceof VoiceRecognitionError
          ? e
          : new VoiceRecognitionError(
              'unknown',
              e instanceof Error ? e.message : 'Voice input failed to start.'
            );

      if (preferred === 'browser' && err.recoverable) {
        // Chrome without a reachable speech service, or a Chromium fork that
        // only pretends to implement the API.
        setDidFallback(true);
      } else if (preferred === 'browser') {
        activeRef.current = false;
        setError(err.message);
        setStatus('error');
        await teardown();
        return;
      }
    }

    if (!(await isVoiceServiceReachable())) {
      activeRef.current = false;
      setError(
        'Speech recognition is unavailable: the voice-to-text service is not running.'
      );
      setStatus('error');
      await teardown();
      return;
    }

    try {
      await startEngine('server', graph);
    } catch (e) {
      activeRef.current = false;
      setError(
        e instanceof Error ? e.message : 'Voice input is unavailable.'
      );
      setStatus('error');
      await teardown();
    }
  }, [startEngine, teardown]);

  const stop = useCallback(async () => {
    if (!activeRef.current) return;
    activeRef.current = false;
    setStatus('finalizing');
    try {
      await recognizerRef.current?.stop();
    } catch {
      /* a failed flush must not block teardown */
    }
    sessionBaseRef.current = join(
      sessionBaseRef.current,
      currentTextRef.current
    );
    currentTextRef.current = '';
    await teardown();
    setStatus('idle');
    setEngine(null);
  }, [teardown]);

  const toggle = useCallback(async () => {
    if (activeRef.current) await stop();
    else await start();
  }, [start, stop]);

  // Never leave the microphone open behind an unmounted component.
  useEffect(() => {
    return () => {
      activeRef.current = false;
      recognizerRef.current?.abort();
      void graphRef.current?.close();
      graphRef.current = null;
    };
  }, []);

  return {
    isRecording: status === 'listening' || status === 'connecting',
    status,
    engine,
    didFallback,
    error,
    analyser,
    start,
    stop,
    toggle,
  };
}
