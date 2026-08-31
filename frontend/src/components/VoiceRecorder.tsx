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
  browser: 'BROWSER_SPEECH',
  server: 'WHISPER_SERVICE',
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

  const busy = status === 'requesting-mic' || status === 'connecting' || status === 'finalizing';

  let statusText = 'TAP_MIC_TO_DICTATE';
  if (status === 'requesting-mic') statusText = 'REQUESTING_MICROPHONE...';
  else if (status === 'connecting') statusText = 'CONNECTING_SPEECH_ENGINE...';
  else if (status === 'listening') statusText = 'LISTENING — SPEAK NOW';
  else if (status === 'finalizing') statusText = 'FINALIZING_TRANSCRIPT...';
  else if (status === 'error') statusText = 'VOICE_INPUT_FAILED';

  return (
    <div className="border border-[#222222] bg-[#0b0b0b]">
      <div className="flex items-center gap-4 p-3">
        <button
          type="button"
          onClick={handleClick}
          disabled={disabled || status === 'finalizing'}
          aria-pressed={isRecording}
          aria-label={isRecording ? 'Stop recording' : 'Start recording'}
          title={isRecording ? 'Stop recording' : 'Dictate your issue'}
          className={`relative shrink-0 w-11 h-11 flex items-center justify-center border transition-all duration-300 disabled:opacity-40 disabled:cursor-not-allowed ${
            isRecording
              ? 'border-[#FF3B3B] bg-[#FF3B3B]/10 text-[#FF3B3B]'
              : 'border-[#00E5FF] bg-[#111111] text-[#00E5FF] hover:bg-[#00E5FF] hover:text-[#050505]'
          }`}
        >
          {isRecording && (
            <span className="absolute inset-0 border border-[#FF3B3B] animate-ping opacity-40" />
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
            color={isRecording ? '#FF3B3B' : '#00E5FF'}
            height={44}
          />
        </div>
      </div>

      <div className="flex items-center justify-between gap-3 border-t border-[#222222] px-3 py-2">
        <span
          className={`text-[10px] font-mono tracking-widest uppercase ${
            status === 'error'
              ? 'text-[#FF3B3B]'
              : status === 'listening'
                ? 'text-[#00E5FF]'
                : 'text-[#666666]'
          }`}
        >
          {busy && status !== 'finalizing' ? (
            <Loader2 className="inline w-3 h-3 mr-1.5 animate-spin align-[-2px]" />
          ) : null}
          {statusText}
        </span>

        {engine && (
          <span className="text-[10px] font-mono tracking-widest uppercase text-[#555555] shrink-0">
            [{ENGINE_LABEL[engine]}]
            {didFallback && engine === 'server' && (
              <span className="text-[#FFD600]"> · FALLBACK</span>
            )}
          </span>
        )}
      </div>

      {error && (
        <div className="flex items-start gap-2 border-t border-[#222222] px-3 py-2 text-[11px] text-[#FF3B3B]">
          <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}
    </div>
  );
}
