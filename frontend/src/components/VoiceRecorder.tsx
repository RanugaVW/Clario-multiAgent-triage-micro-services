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
    <div className="rounded-2xl backdrop-blur-md bg-white/[0.03] border border-white/[0.08] overflow-hidden">
      <div className="flex items-center gap-4 p-3">
        <button
          type="button"
          onClick={handleClick}
          disabled={disabled || status === 'finalizing'}
          aria-pressed={isRecording}
          aria-label={isRecording ? 'Stop recording' : 'Start recording'}
          title={isRecording ? 'Stop recording' : 'Dictate your issue'}
          className={`relative shrink-0 w-11 h-11 rounded-full flex items-center justify-center border transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed ${
            isRecording
              ? 'border-[#FB7185] bg-[#FB7185]/10 text-[#FB7185]'
              : 'border-[#2DD4BF] bg-white/[0.04] text-[#2DD4BF] hover:bg-[#2DD4BF] hover:text-[#08090D]'
          }`}
        >
          {isRecording && (
            <span className="absolute inset-0 rounded-full border border-[#FB7185] animate-ping opacity-40" />
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
            color={isRecording ? '#FB7185' : '#2DD4BF'}
            height={44}
          />
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-white/10 px-3 py-2">
        <span
          className={`text-xs ${
            status === 'error'
              ? 'text-[#FB7185]'
              : status === 'listening'
                ? 'text-[#2DD4BF]'
                : 'text-[#8A8F98]'
          }`}
        >
          {busy && status !== 'finalizing' ? (
            <Loader2 className="inline w-3 h-3 mr-1.5 animate-spin align-[-2px]" />
          ) : null}
          {statusText}
        </span>

        {engine && (
          <span className="text-xs text-[#8A8F98] shrink-0">
            {ENGINE_LABEL[engine]}
            {didFallback && engine === 'server' && (
              <span className="text-[#FB923C]"> · fallback</span>
            )}
          </span>
        )}
      </div>

      {error && (
        <div className="flex items-start gap-2 border-t border-white/10 px-3 py-2 text-[11px] text-[#FB7185]">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
