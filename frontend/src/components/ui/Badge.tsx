import type { HTMLAttributes } from 'react';
import { cx } from '../../lib/cx';

export type BadgeTone = 'neutral' | 'brand' | 'accent' | 'success' | 'warning' | 'danger' | 'info';

const TONES: Record<BadgeTone, string> = {
  neutral: 'border-border bg-surface-raised text-fg-muted',
  brand: 'border-transparent bg-brand-soft text-brand',
  accent: 'border-transparent bg-accent/15 text-accent',
  success: 'border-transparent bg-success/15 text-success',
  warning: 'border-transparent bg-warning/15 text-warning',
  danger: 'border-transparent bg-danger/15 text-danger',
  info: 'border-transparent bg-info/15 text-info',
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
