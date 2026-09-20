'use client';

import { useCallback, useRef } from 'react';
import { AlertCircle, Loader2, Mic, Square } from 'lucide-react';

import AudioWaveform from './AudioWaveform';
import { useVoiceInput } from '../hooks/useVoiceInput';

interface VoiceRecorderProps {
  /** Current field value; captured as the prefix when recording starts. */
  value: string;
  onValueChange: (next: string) => void;
  disabled?: boolean;
  lang?: string;
}

const ENGINE_LABEL = {
  browser: 'Browser speech',
  server: 'Whisper service',
} as const;

/**
 * Mic button + live waveform + dictated text, wired straight into a text field.
 *
 * Transcripts are appended to whatever the field already held when recording
 * started, so dictation adds to a typed draft instead of replacing it.
 */
export default function VoiceRecorder({
  value,
  onValueChange,
  disabled = false,
  lang = 'en-US',
}: VoiceRecorderProps) {
  // Snapshot of the field taken at record time; live transcripts append to it.
  const baseTextRef = useRef('');

  const handleTranscript = useCallback(
    (transcript: string) => {
      const base = baseTextRef.current;
      if (!transcript) {
        onValueChange(base);
        return;
      }
      onValueChange(base ? `${base.trimEnd()} ${transcript}` : transcript);
    },
    [onValueChange]
  );

  const { isRecording, status, engine, didFallback, error, analyser, toggle } =
    useVoiceInput({ onTranscript: handleTranscript, lang });

  const handleClick = useCallback(async () => {
    if (!isRecording) baseTextRef.current = value;
    await toggle();
  }, [isRecording, toggle, value]);

  const busy =
    status === 'requesting-mic' ||
    status === 'connecting' ||
    status === 'finalizing';

  let statusText = 'Tap to start dictating';
  if (status === 'requesting-mic') statusText = 'Requesting microphone access…';
  else if (status === 'connecting') statusText = 'Connecting…';
  else if (status === 'listening') statusText = 'Listening, go ahead';
  else if (status === 'finalizing') statusText = 'Finalizing…';
  else if (status === 'error') statusText = 'Voice input failed';

  return (
    <div className="overflow-hidden rounded-lg border border-border bg-surface">
      <div className="flex items-center gap-4 p-3">
        <button
          type="button"
          onClick={handleClick}
          disabled={disabled || status === 'finalizing'}
          aria-pressed={isRecording}
          aria-label={isRecording ? 'Stop recording' : 'Start recording'}
          title={isRecording ? 'Stop recording' : 'Dictate your issue'}
          className={`relative flex h-11 w-11 shrink-0 items-center justify-center rounded-full border transition-colors duration-300 disabled:cursor-not-allowed disabled:opacity-40 ${
            isRecording
              ? 'border-danger bg-surface text-danger'
              : 'border-accent bg-surface text-accent hover:bg-accent hover:text-canvas'
          }`}
        >
          {isRecording && (
            <span className="absolute inset-0 animate-ping rounded-full border border-danger opacity-40" />
          )}
          {status === 'finalizing' ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : isRecording ? (
            <Square className="w-4 h-4 fill-current" />
          ) : (
            <Mic className="w-4 h-4" />
          )}
        </button>

        <div className="flex-1 min-w-0">
          <AudioWaveform
            analyser={analyser}
            active={status === 'listening'}
            color={isRecording ? 'var(--c-danger)' : 'var(--c-accent)'}
            height={44}
          />
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-border px-3 py-2">
        <span
          className={`text-caption ${
            status === 'error'
              ? 'text-danger'
              : status === 'listening'
                ? 'text-accent'
                : 'text-fg-muted'
          }`}
        >
          {busy && status !== 'finalizing' ? (
            <Loader2 className="inline w-3 h-3 mr-1.5 animate-spin align-[-2px]" />
          ) : null}
          {statusText}
        </span>

        {engine && (
          <span className="shrink-0 text-caption text-fg-muted">
            {ENGINE_LABEL[engine]}
            {didFallback && engine === 'server' && (
              <span className="text-warning"> · fallback</span>
            )}
          </span>
        )}
      </div>

      {error && (
        <div className="flex items-start gap-2 border-t border-border px-3 py-2 text-caption text-danger">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
