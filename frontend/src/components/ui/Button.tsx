import Link from 'next/link';
import type { ButtonHTMLAttributes, ComponentProps } from 'react';
import { cx } from '../../lib/cx';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive';
export type ButtonSize = 'sm' | 'md' | 'lg';

const BASE =
  'inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium transition-colors disabled:pointer-events-none disabled:opacity-50';

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-brand text-brand-fg hover:bg-brand-hover',
  secondary: 'border border-border-strong bg-surface text-fg hover:bg-surface-raised',
  ghost: 'text-fg-muted hover:bg-brand-soft hover:text-fg',
  // brand-fg is the "text on a solid color" token; it is readable on danger in both modes.
  destructive: 'bg-danger text-brand-fg hover:opacity-90',
};

const SIZES: Record<ButtonSize, string> = {
  sm: 'h-8 rounded-md px-3 text-small',
  md: 'h-10 rounded-lg px-4 text-app',
  lg: 'h-12 rounded-lg px-6 text-body',
};

interface StyleProps {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

export function buttonClass({
  variant = 'primary',
  size = 'md',
  className,
}: StyleProps & { className?: string } = {}): string {
  return cx(BASE, VARIANTS[variant], SIZES[size], className);
}

export function Button({
  variant,
  size,
  className,
  type = 'button',
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & StyleProps) {
  return <button type={type} className={buttonClass({ variant, size, className })} {...rest} />;
}

export function ButtonLink({ variant, size, className, ...rest }: ComponentProps<typeof Link> & StyleProps) {
  return <Link className={buttonClass({ variant, size, className })} {...rest} />;
}
