import type { ReactNode } from 'react';
import { cx } from '../../lib/cx';

export type NoticeTone = 'success' | 'danger' | 'info';

// A solid surface with a tone-colored border and text. The tone text colors are contrast-tested against the
// surface tokens in src/theme/theme.config.test.ts, so no tinted fill is used.
const TONES: Record<NoticeTone, string> = {
  success: 'border-success/40 text-success',
  danger: 'border-danger/40 text-danger',
  info: 'border-info/40 text-info',
};

/** Pass `role="alert"` for errors that appear after an action and `role="status"` for confirmations. */
export function Notice({
  tone,
  role,
  title,
  className,
  children,
}: {
  tone: NoticeTone;
  role?: 'alert' | 'status';
  title?: string;
  className?: string;
  children: ReactNode;
}) {
  return (
    <div role={role} className={cx('rounded-lg border bg-surface p-4 text-app', TONES[tone], className)}>
      {title && <p className="font-medium">{title}</p>}
      <div className={title ? 'mt-1 text-fg-muted' : undefined}>{children}</div>
    </div>
  );
}
