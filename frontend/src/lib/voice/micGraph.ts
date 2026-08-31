/**
 * Owns the microphone and the Web Audio graph both engines share.
 *
 * The analyser node feeds the live waveform, and the same source node is what
 * the PCM worklet taps when we stream to the whisper service - so switching
 * engines mid-recording never has to re-prompt for the microphone.
 */

import { VoiceRecognitionError } from './types';

export const TARGET_SAMPLE_RATE = 16000;

export interface MicGraph {
  stream: MediaStream;
  context: AudioContext;
  source: MediaStreamAudioSourceNode;
  analyser: AnalyserNode;
  close: () => Promise<void>;
}

function createContext(): AudioContext {
  const Ctor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!Ctor) {
    throw new VoiceRecognitionError(
      'unsupported',
      'This browser has no Web Audio support.',
      false
    );
  }
  try {
    // Asking for 16 kHz up front lets the browser resample for us. Browsers are
    // free to ignore it, which is why the worklet resamples as well.
    return new Ctor({ sampleRate: TARGET_SAMPLE_RATE });
  } catch {
    return new Ctor();
  }
}

export async function openMicGraph(): Promise<MicGraph> {
  if (typeof navigator === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
    throw new VoiceRecognitionError(
      'unsupported',
      'Microphone capture is not available in this browser.',
      false
    );
  }

  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
  } catch (e) {
    const name = e instanceof Error ? e.name : '';
    if (name === 'NotAllowedError' || name === 'SecurityError') {
      throw new VoiceRecognitionError(
        'mic-denied',
        'Microphone permission was denied.',
        false
      );
    }
    throw new VoiceRecognitionError('no-mic', 'No microphone was found.', false);
  }

  let context: AudioContext;
  let source: MediaStreamAudioSourceNode;
  let analyser: AnalyserNode;
  try {
    context = createContext();
    if (context.state === 'suspended') {
      await context.resume().catch(() => undefined);
    }
    source = context.createMediaStreamSource(stream);
    analyser = context.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.75;
    source.connect(analyser);
  } catch (e) {
    // Releasing the microphone matters more than the failure itself; leaving
    // it open would keep the browser's recording indicator lit.
    stream.getTracks().forEach((track) => track.stop());
    throw e;
  }

  return {
    stream,
    context,
    source,
    analyser,
    close: async () => {
      try {
        source.disconnect();
      } catch {
        /* already disconnected */
      }
      stream.getTracks().forEach((track) => track.stop());
      if (context.state !== 'closed') {
        await context.close().catch(() => undefined);
      }
    },
  };
}
