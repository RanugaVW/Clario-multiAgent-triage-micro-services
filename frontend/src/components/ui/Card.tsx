import type { HTMLAttributes } from 'react';
import { cx } from '../../lib/cx';

export function Card({ raised = false, flush = false, className, ...rest }: HTMLAttributes<HTMLDivElement> & { raised?: boolean; flush?: boolean }) {
  return (
    <div
      className={cx(
        'rounded-xl border border-border',
        !flush && 'p-card',
        raised ? 'bg-surface-raised shadow-raised' : 'bg-surface shadow-card',
        className
      )}
      {...rest}
    />
  );
}
