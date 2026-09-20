'use client';

import { useEffect, useRef, type ReactNode } from 'react';
import { cx } from '../../lib/cx';

export type NoticeTone = 'success' | 'danger' | 'info';

// A solid surface with a tone-colored border and text. The tone text colors are contrast-tested against the
// surface tokens in src/theme/theme.config.test.ts, so no tinted fill is used.
const TONES: Record<NoticeTone, string> = {
  success: 'border-success/40 text-success',
  danger: 'border-danger/40 text-danger',
  info: 'border-info/40 text-info',
};

/**
 * Pass `role="alert"` for errors that appear after an action and `role="status"` for confirmations.
 * `focusOnMount` moves keyboard focus to the notice when it appears; use it when a notice replaces the
 * form the user just submitted (otherwise focus is lost with the removed button).
 */
export function Notice({
  tone,
  role,
  title,
  className,
  focusOnMount,
  children,
}: {
  tone: NoticeTone;
  role?: 'alert' | 'status';
  title?: string;
  className?: string;
  focusOnMount?: boolean;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (focusOnMount) ref.current?.focus();
  }, [focusOnMount]);

  return (
    <div
      ref={ref}
      tabIndex={focusOnMount ? -1 : undefined}
      role={role}
      className={cx('rounded-lg border bg-surface p-4 text-app', TONES[tone], className)}
    >
      {title && <p className="font-medium">{title}</p>}
      <div className={title ? 'mt-1 text-fg-muted' : undefined}>{children}</div>
    </div>
  );
}
