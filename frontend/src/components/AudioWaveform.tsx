'use client';

import { useEffect, useRef } from 'react';

interface AudioWaveformProps {
  /** Live analyser from the microphone graph, or null when not recording. */
  analyser: AnalyserNode | null;
  active: boolean;
  color?: string;
  height?: number;
  className?: string;
}

/**
 * Mirror-bar visualiser driven by the analyser's time-domain data.
 *
 * Bars are drawn from RMS over slices of the waveform rather than raw samples,
 * which reads as "how loud am I right now" instead of a jittery oscilloscope.
 */
export default function AudioWaveform({
  analyser,
  active,
  color = '#00E5FF',
  height = 56,
  className = '',
}: AudioWaveformProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const frameRef = useRef<number | null>(null);
  // Persisted between frames so bars decay smoothly instead of snapping.
  const levelsRef = useRef<number[]>([]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const BAR_WIDTH = 3;
    const BAR_GAP = 3;

    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      return rect.width;
    };

    let cssWidth = resize();
    const observer = new ResizeObserver(() => {
      cssWidth = resize();
    });
    observer.observe(canvas);

    const buffer = analyser ? new Uint8Array(analyser.fftSize) : null;

    const draw = () => {
      const barCount = Math.max(1, Math.floor(cssWidth / (BAR_WIDTH + BAR_GAP)));
      if (levelsRef.current.length !== barCount) {
        levelsRef.current = new Array(barCount).fill(0);
      }
      const levels = levelsRef.current;

      let level = 0;
      if (active && analyser && buffer) {
        analyser.getByteTimeDomainData(buffer);
        let sum = 0;
        for (let i = 0; i < buffer.length; i++) {
          const centred = (buffer[i] - 128) / 128;
          sum += centred * centred;
        }
        const rms = Math.sqrt(sum / buffer.length);
        // Compress the range so normal speech fills most of the bar height.
        level = Math.min(1, Math.pow(rms * 3.2, 0.7));
      }

      levels.shift();
      levels.push(level);

      ctx.clearRect(0, 0, cssWidth, height);
      const mid = height / 2;

      for (let i = 0; i < levels.length; i++) {
        const value = levels[i];
        const barHeight = Math.max(2, value * (height - 6));
        const x = i * (BAR_WIDTH + BAR_GAP);
        // Older samples scroll left and fade out.
        const age = i / Math.max(1, levels.length - 1);
        ctx.globalAlpha = active ? 0.25 + age * 0.75 : 0.18;
        ctx.fillStyle = color;
        ctx.fillRect(x, mid - barHeight / 2, BAR_WIDTH, barHeight);
      }
      ctx.globalAlpha = 1;

      frameRef.current = requestAnimationFrame(draw);
    };

    frameRef.current = requestAnimationFrame(draw);

    return () => {
      if (frameRef.current !== null) cancelAnimationFrame(frameRef.current);
      observer.disconnect();
    };
  }, [analyser, active, color, height]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={`w-full block ${className}`}
      style={{ height }}
    />
  );
}
