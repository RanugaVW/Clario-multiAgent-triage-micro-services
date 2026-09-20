import type { HTMLAttributes } from 'react';
import { cx } from '../../lib/cx';

type Size = 'marketing' | 'app';

const WIDTH: Record<Size, string> = { marketing: 'max-w-marketing', app: 'max-w-app' };

export function Container({ size = 'marketing', className, ...rest }: HTMLAttributes<HTMLDivElement> & { size?: Size }) {
  return <div className={cx('mx-auto w-full px-page', WIDTH[size], className)} {...rest} />;
}

export function Section({
  size = 'marketing',
  contained = true,
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLElement> & { size?: Size; contained?: boolean }) {
  return (
    <section className={cx('py-section', className)} {...rest}>
      {contained ? <Container size={size}>{children}</Container> : children}
    </section>
  );
}
