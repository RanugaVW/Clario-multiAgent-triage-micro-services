import { cx } from '../../lib/cx';

/**
 * Soft theme-colored glow behind a section. Purely decorative. The parent must be `relative` (and usually
 * `overflow-hidden`); content that sits above it needs `relative` too. The drift animation is defined in globals.css.
 */
export function GlowBackdrop({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" className={cx('pointer-events-none absolute inset-0 overflow-hidden', className)}>
      <div className="glow-blob absolute left-1/2 top-[-12rem] h-[36rem] w-[60rem] max-w-none -translate-x-1/2" />
    </div>
  );
}
