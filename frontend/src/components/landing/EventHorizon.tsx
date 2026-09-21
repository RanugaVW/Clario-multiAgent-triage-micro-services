import type { CSSProperties } from 'react';
import { cx } from '../../lib/cx';

// Ticket streaks: --x is the start offset from the centre line, --d the animation delay (negative = already in flight).
const STREAKS = [
  { x: '-15rem', d: '-0.4s' },
  { x: '-7rem', d: '-1.8s' },
  { x: '0rem', d: '-3s' },
  { x: '8rem', d: '-1.1s' },
  { x: '16rem', d: '-2.4s' },
] as const;

/**
 * Decorative glowing ring that rises from the top edge of its `relative` parent, with ticket streaks falling into it.
 * Colours come from theme.horizon (--hz-*); only transform and opacity are animated (see globals.css).
 */
export function EventHorizon({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cx('hz', className)}>
      <div className="hz-halo" />
      <div className="hz-stars" />
      <div className="hz-outer" />
      <div className="hz-ring" />
      <div className="hz-sweep" />
      <div className="hz-ring-alt" />
      <div className="hz-void" />
      <div className="hz-line" />
      {STREAKS.map((s) => (
        <span key={s.x} className="hz-streak" style={{ '--x': s.x, '--d': s.d } as CSSProperties} />
      ))}
    </div>
  );
}

/** Soft glow reflected onto the panel below the horizon. The parent must be `relative`. */
export function EventHorizonReflection({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cx('hz-reflect', className)} />;
}
