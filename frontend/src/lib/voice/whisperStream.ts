/**
 * Streaming client for the faster-whisper voice-to-text microservice.
 *
 * Raw 16 kHz int16 PCM goes up the socket as binary frames; `partial` and
 * `final` transcript messages come back down as JSON. This is the fallback
 * engine for every browser without a working Web Speech API, and it works
 * identically in Chrome.
 */

import type { MicGraph } from './micGraph';
import { TARGET_SAMPLE_RATE } from './micGraph';
import {
  Recognizer,
  RecognizerHandlers,
  VoiceRecognitionError,
} from './types';

const WORKLET_URL = '/worklets/pcm-recorder.js';
const OPEN_TIMEOUT_MS = 8000;
const FINALIZE_TIMEOUT_MS = 20000;

export function getVoiceServiceHttpUrl(): string {
  return (
    process.env.NEXT_PUBLIC_VOICE_SERVICE_URL || 'http://127.0.0.1:8002'
  ).replace(/\/$/, '');
}

export function getVoiceServiceWsUrl(): string {
  const explicit = process.env.NEXT_PUBLIC_VOICE_WS_URL;
  if (explicit) return explicit;
  const http = getVoiceServiceHttpUrl();
  return `${http.replace(/^http/, 'ws')}/ws/transcribe`;
}

/** Cheap reachability probe so we can report a clear error instead of hanging. */
export async function isVoiceServiceReachable(
  timeoutMs = 2500
): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${getVoiceServiceHttpUrl()}/health`, {
      signal: controller.signal,
    });
    return res.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

type ServerMessage = {
  type: 'ready' | 'partial' | 'final' | 'error';
  transcript?: string;
  committed?: string;
  partial?: string;
  is_final?: boolean;
  message?: string;
};

export class WhisperStreamRecognizer implements Recognizer {
  readonly engine = 'server' as const;

  private handlers: RecognizerHandlers;
  private url: string;
  private socket: WebSocket | null = null;
  private worklet: AudioWorkletNode | null = null;
  private legacyNode: ScriptProcessorNode | null = null;
  private sink: GainNode | null = null;

  private lastTranscript = '';
  private stopping = false;
  private finalResolve: (() => void) | null = null;

  constructor(handlers: RecognizerHandlers, url = getVoiceServiceWsUrl()) {
    this.handlers = handlers;
    this.url = url;
  }

  async start(graph: MicGraph): Promise<void> {
    await this.openSocket();
    await this.attachCapture(graph);
  }

  private openSocket(): Promise<void> {
    return new Promise<void>((resolve, reject) => {
      let socket: WebSocket;
      try {
        socket = new WebSocket(this.url);
      } catch (e) {
        reject(
          new VoiceRecognitionError(
            'service-unavailable',
            e instanceof Error ? e.message : 'Could not open the voice socket.'
          )
        );
        return;
      }

      socket.binaryType = 'arraybuffer';
      this.socket = socket;

      let settled = false;
      const timer = setTimeout(() => {
        if (settled) return;
        settled = true;
        try {
          socket.close();
        } catch {
          /* noop */
        }
        reject(
          new VoiceRecognitionError(
            'service-unavailable',
            'The voice-to-text service did not respond.'
          )
        );
      }, OPEN_TIMEOUT_MS);

      socket.onopen = () => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        resolve();
      };

      socket.onerror = () => {
        if (settled) {
          if (!this.stopping) {
            this.handlers.onError(
              new VoiceRecognitionError(
                'network',
                'Lost connection to the voice-to-text service.'
              )
            );
          }
          return;
        }
        settled = true;
        clearTimeout(timer);
        reject(
          new VoiceRecognitionError(
            'service-unavailable',
            'Could not reach the voice-to-text service.'
          )
        );
      };

      socket.onmessage = (event) => this.handleMessage(event);

      socket.onclose = () => {
        // A close without a `final` message still has to release `stop()`.
        this.finalResolve?.();
        this.finalResolve = null;
      };
    });
  }

  private handleMessage(event: MessageEvent) {
    if (typeof event.data !== 'string') return;
    let message: ServerMessage;
    try {
      message = JSON.parse(event.data);
    } catch {
      return;
    }

    if (message.type === 'error') {
      this.handlers.onError(
        new VoiceRecognitionError(
          'service-unavailable',
          message.message || 'The voice-to-text service reported an error.'
        )
      );
      return;
    }

    if (message.type === 'partial' || message.type === 'final') {
      this.lastTranscript = message.transcript ?? this.lastTranscript;
      this.handlers.onUpdate({
        transcript: message.transcript ?? '',
        committed: message.committed ?? '',
        partial: message.partial ?? '',
        isFinal: message.type === 'final',
      });
      if (message.type === 'final') {
        this.finalResolve?.();
        this.finalResolve = null;
      }
    }
  }

  private async attachCapture(graph: MicGraph) {
    const { context, source } = graph;

    // A muted sink keeps the graph pulling audio; some browsers stall a branch
    // that never reaches a destination.
    const sink = context.createGain();
    sink.gain.value = 0;
    sink.connect(context.destination);
    this.sink = sink;

    const send = (buffer: ArrayBuffer) => {
      const socket = this.socket;
      if (socket?.readyState === WebSocket.OPEN) socket.send(buffer);
    };

    if (context.audioWorklet) {
      try {
        await context.audioWorklet.addModule(WORKLET_URL);
        const node = new AudioWorkletNode(context, 'pcm-recorder', {
          numberOfInputs: 1,
          numberOfOutputs: 1,
          channelCount: 1,
          processorOptions: { targetSampleRate: TARGET_SAMPLE_RATE },
        });
        node.port.onmessage = (event) => send(event.data as ArrayBuffer);
        source.connect(node);
        node.connect(sink);
        this.worklet = node;
        return;
      } catch {
        // Fall through to the ScriptProcessor path below.
      }
    }

    this.attachLegacyCapture(graph, sink, send);
  }

  /** ScriptProcessorNode path for browsers without a usable AudioWorklet. */
  private attachLegacyCapture(
    graph: MicGraph,
    sink: GainNode,
    send: (buffer: ArrayBuffer) => void
  ) {
    const { context, source } = graph;
    const node = context.createScriptProcessor(4096, 1, 1);
    const ratio = context.sampleRate / TARGET_SAMPLE_RATE;

    node.onaudioprocess = (event) => {
      const input = event.inputBuffer.getChannelData(0);
      const outLength = Math.floor(input.length / ratio);
      const out = new Int16Array(outLength);
      for (let i = 0; i < outLength; i++) {
        const pos = i * ratio;
        const index = Math.floor(pos);
        const frac = pos - index;
        const next = index + 1 < input.length ? input[index + 1] : input[index];
        const value = Math.max(-1, Math.min(1, input[index] * (1 - frac) + next * frac));
        out[i] = value < 0 ? value * 0x8000 : value * 0x7fff;
      }
      send(out.buffer);
    };

    source.connect(node);
    node.connect(sink);
    this.legacyNode = node;
  }

  async stop(): Promise<void> {
    this.stopping = true;
    this.detachCapture();

    const socket = this.socket;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      this.cleanup();
      return;
    }

    const waitForFinal = new Promise<void>((resolve) => {
      this.finalResolve = resolve;
      setTimeout(() => {
        if (this.finalResolve) {
          this.finalResolve = null;
          resolve();
        }
      }, FINALIZE_TIMEOUT_MS);
    });

    try {
      socket.send(JSON.stringify({ type: 'stop' }));
    } catch {
      this.cleanup();
      return;
    }

    await waitForFinal;
    this.cleanup();
  }

  abort(): void {
    this.stopping = true;
    this.detachCapture();
    this.cleanup();
  }

  private detachCapture() {
    if (this.worklet) {
      try {
        this.worklet.port.postMessage('stop');
        this.worklet.disconnect();
      } catch {
        /* noop */
      }
      this.worklet = null;
    }
    if (this.legacyNode) {
      try {
        this.legacyNode.onaudioprocess = null;
        this.legacyNode.disconnect();
      } catch {
        /* noop */
      }
      this.legacyNode = null;
    }
  }

  private cleanup() {
    if (this.sink) {
      try {
        this.sink.disconnect();
      } catch {
        /* noop */
      }
      this.sink = null;
    }
    const socket = this.socket;
    this.socket = null;
    if (socket) {
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;
      try {
        socket.close();
      } catch {
        /* noop */
      }
    }
  }

  get transcript(): string {
    return this.lastTranscript;
  }
}
