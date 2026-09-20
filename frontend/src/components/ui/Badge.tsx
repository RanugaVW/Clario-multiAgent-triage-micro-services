import type { HTMLAttributes } from 'react';
import { cx } from '../../lib/cx';

export type BadgeTone = 'neutral' | 'brand' | 'accent' | 'success' | 'warning' | 'danger' | 'info';

// Text sits on a SOLID surface, whose contrast against every tone theme.config.test.ts guarantees. A
// translucent tint would darken/lighten the fill and can drop small text below 4.5:1, so the tone is carried
// by the text colour and a 40% border instead.
const TONES: Record<BadgeTone, string> = {
  neutral: 'border-border bg-surface-raised text-fg-muted',
  brand: 'border-brand/40 bg-surface text-brand',
  accent: 'border-accent/40 bg-surface text-accent',
  success: 'border-success/40 bg-surface text-success',
  warning: 'border-warning/40 bg-surface text-warning',
  danger: 'border-danger/40 bg-surface text-danger',
  info: 'border-info/40 bg-surface text-info',
};

export function Badge({
  tone = 'neutral',
  className,
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cx('inline-flex items-center gap-1 rounded-pill border px-2.5 py-0.5 text-caption', TONES[tone], className)}
      {...rest}
    />
  );
}
