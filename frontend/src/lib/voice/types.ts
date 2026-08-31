/** Shared contracts for the two speech-recognition engines. */

import type { MicGraph } from './micGraph';

/**
 * `browser` is the Google Web Speech API built into Chrome / Edge.
 * `server` is the self-hosted faster-whisper voice-to-text microservice.
 */
export type VoiceEngine = 'browser' | 'server';

export type VoiceStatus =
  | 'idle'
  | 'requesting-mic'
  | 'connecting'
  | 'listening'
  | 'finalizing'
  | 'error';

export interface TranscriptUpdate {
  /** Everything recognised so far, stable prefix plus the moving tail. */
  transcript: string;
  /** The part that will not change any more. */
  committed: string;
  /** The tail that may still be revised. */
  partial: string;
  isFinal: boolean;
}

export interface RecognizerHandlers {
  onUpdate: (update: TranscriptUpdate) => void;
  /** Fatal for this engine - the caller decides whether to fall back. */
  onError: (error: VoiceRecognitionError) => void;
}

export type VoiceErrorCode =
  | 'unsupported'
  | 'mic-denied'
  | 'no-mic'
  | 'network'
  | 'service-unavailable'
  | 'aborted'
  | 'unknown';

export class VoiceRecognitionError extends Error {
  code: VoiceErrorCode;
  /** Whether trying the other engine is worth it. */
  recoverable: boolean;

  constructor(code: VoiceErrorCode, message: string, recoverable = true) {
    super(message);
    this.name = 'VoiceRecognitionError';
    this.code = code;
    this.recoverable = recoverable;
  }
}

export interface Recognizer {
  readonly engine: VoiceEngine;
  /** `graph` is the shared microphone graph; the browser engine ignores it. */
  start(graph: MicGraph): Promise<void>;
  /** Resolves once the final transcript has been delivered. */
  stop(): Promise<void>;
  /** Tear down without waiting for a final transcript. */
  abort(): void;
}
