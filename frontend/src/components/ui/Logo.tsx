import { cx } from '../../lib/cx';
import { theme } from '../../theme/theme.config';

export function Logo({ showName = true, className }: { showName?: boolean; className?: string }) {
  const { mark, name } = theme.brand;
  return (
    <span className={cx('inline-flex items-center gap-2 text-fg', className)}>
      <svg
        viewBox={mark.viewBox}
        width="24"
        height="24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        className="text-brand"
        aria-hidden="true"
      >
        <path d={mark.path} />
        {mark.dot && <circle cx={mark.dot.cx} cy={mark.dot.cy} r={mark.dot.r} fill="currentColor" stroke="none" />}
      </svg>
      <span className={showName ? 'text-body font-semibold tracking-tight' : 'sr-only'}>{name}</span>
    </span>
  );
}
