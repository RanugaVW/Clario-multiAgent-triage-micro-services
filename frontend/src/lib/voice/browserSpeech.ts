/**
 * Chrome / Edge speech recognition via the Google-backed Web Speech API.
 *
 * This is the preferred path when it works: recognition happens without the
 * browser shipping audio to our own infrastructure and latency is excellent.
 * Everywhere else - Firefox, Safari, Chromium builds without the Google speech
 * service - `isBrowserSpeechSupported()` returns false or the recognizer fails
 * fast, and the caller falls back to the whisper microservice.
 */

import {
  Recognizer,
  RecognizerHandlers,
  VoiceRecognitionError,
} from './types';

/** Milliseconds to wait for `onstart` before declaring the engine dead. */
const START_TIMEOUT_MS = 4000;

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  start: () => void;
  stop: () => void;
  abort: () => void;
  onstart: ((event: Event) => void) | null;
  onend: ((event: Event) => void) | null;
  onerror: ((event: { error: string; message?: string }) => void) | null;
  onresult: ((event: SpeechRecognitionResultLikeEvent) => void) | null;
};

type SpeechRecognitionResultLikeEvent = {
  resultIndex: number;
  results: ArrayLike<{
    isFinal: boolean;
    length: number;
    0: { transcript: string };
  }>;
};

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;

function getConstructor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export function isBrowserSpeechSupported(): boolean {
  return getConstructor() !== null;
}

export class BrowserSpeechRecognizer implements Recognizer {
  readonly engine = 'browser' as const;

  private recognition: SpeechRecognitionLike | null = null;
  private handlers: RecognizerHandlers;
  private lang: string;

  private committed = '';
  private partial = '';
  private running = false;
  /** Set while `stop()` is waiting for the engine to wind down. */
  private stopResolve: (() => void) | null = null;

  constructor(handlers: RecognizerHandlers, lang = 'en-US') {
    this.handlers = handlers;
    this.lang = lang;
  }

  /**
   * The Web Speech API opens its own microphone capture, so the shared
   * `MediaStream` is only used by the caller for the waveform display.
   */
  start(): Promise<void> {
    const Ctor = getConstructor();
    if (!Ctor) {
      return Promise.reject(
        new VoiceRecognitionError(
          'unsupported',
          'This browser has no Web Speech API.'
        )
      );
    }

    const recognition = new Ctor();
    this.recognition = recognition;
    recognition.lang = this.lang;
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    return new Promise<void>((resolve, reject) => {
      let settled = false;
      const timer = setTimeout(() => {
        if (settled) return;
        settled = true;
        this.teardown();
        reject(
          new VoiceRecognitionError(
            'service-unavailable',
            'The browser speech service did not start.'
          )
        );
      }, START_TIMEOUT_MS);

      const settle = (error?: VoiceRecognitionError) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (error) reject(error);
        else resolve();
      };

      recognition.onstart = () => {
        this.running = true;
        settle();
      };

      recognition.onresult = (event) => {
        let interim = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const result = event.results[i];
          const text = result[0]?.transcript ?? '';
          if (result.isFinal) {
            this.committed = joinText(this.committed, text.trim());
          } else {
            interim = joinText(interim, text.trim());
          }
        }
        this.partial = interim;
        this.emit(false);
      };

      recognition.onerror = (event) => {
        const error = mapError(event.error, event.message);
        // `no-speech` just means a quiet stretch - Chrome ends the session but
        // there is nothing wrong, so let `onend` restart it.
        if (event.error === 'no-speech' || event.error === 'aborted') return;
        if (!settled) this.teardown();
        settle(error);
        if (this.running) {
          this.running = false;
          this.handlers.onError(error);
        }
      };

      recognition.onend = () => {
        // Chrome ends a continuous session after long silences; restart it
        // unless the caller actually asked us to stop.
        if (this.running) {
          try {
            recognition.start();
            return;
          } catch {
            this.running = false;
          }
        }
        this.partial = '';
        this.emit(true);
        this.stopResolve?.();
        this.stopResolve = null;
      };

      try {
        recognition.start();
      } catch (e) {
        settle(
          new VoiceRecognitionError(
            'service-unavailable',
            e instanceof Error ? e.message : 'Failed to start recognition.'
          )
        );
      }
    });
  }

  stop(): Promise<void> {
    const recognition = this.recognition;
    if (!recognition || !this.running) {
      this.emit(true);
      return Promise.resolve();
    }
    this.running = false;
    return new Promise<void>((resolve) => {
      this.stopResolve = resolve;
      // Guard against `onend` never arriving.
      setTimeout(() => {
        if (this.stopResolve) {
          this.stopResolve = null;
          this.emit(true);
          resolve();
        }
      }, 1500);
      try {
        recognition.stop();
      } catch {
        this.stopResolve = null;
        this.emit(true);
        resolve();
      }
    });
  }

  abort(): void {
    this.running = false;
    this.teardown();
  }

  private teardown() {
    const recognition = this.recognition;
    this.recognition = null;
    if (!recognition) return;
    recognition.onstart = null;
    recognition.onend = null;
    recognition.onerror = null;
    recognition.onresult = null;
    try {
      recognition.abort();
    } catch {
      /* already gone */
    }
  }

  private emit(isFinal: boolean) {
    this.handlers.onUpdate({
      transcript: joinText(this.committed, this.partial),
      committed: this.committed,
      partial: this.partial,
      isFinal,
    });
  }
}

function joinText(a: string, b: string): string {
  if (!a) return b;
  if (!b) return a;
  return `${a} ${b}`;
}

function mapError(code: string, message?: string): VoiceRecognitionError {
  switch (code) {
    case 'not-allowed':
      return new VoiceRecognitionError(
        'mic-denied',
        'Microphone permission was denied.',
        false
      );
    case 'audio-capture':
      return new VoiceRecognitionError(
        'no-mic',
        'No microphone was found.',
        false
      );
    case 'network':
      return new VoiceRecognitionError(
        'network',
        'The browser speech service is unreachable.'
      );
    case 'service-not-allowed':
    case 'language-not-supported':
      return new VoiceRecognitionError(
        'service-unavailable',
        message || 'The browser speech service refused the request.'
      );
    default:
      return new VoiceRecognitionError(
        'unknown',
        message || `Speech recognition failed (${code}).`
      );
  }
}
