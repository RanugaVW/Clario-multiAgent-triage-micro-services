import type { HTMLAttributes } from 'react';
import { cx } from '../../lib/cx';

export function Card({ raised = false, className, ...rest }: HTMLAttributes<HTMLDivElement> & { raised?: boolean }) {
  return (
    <div
      className={cx(
        'rounded-xl border border-border p-card',
        raised ? 'bg-surface-raised shadow-raised' : 'bg-surface shadow-card',
        className
      )}
      {...rest}
    />
  );
}
