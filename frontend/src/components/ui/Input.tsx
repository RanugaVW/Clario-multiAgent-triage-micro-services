'use client';

import { Eye, EyeOff } from 'lucide-react';
import { useState, type InputHTMLAttributes, type TextareaHTMLAttributes } from 'react';
import { cx } from '../../lib/cx';

const FIELD =
  'w-full rounded-lg border border-border-strong bg-surface px-3.5 py-2.5 text-app text-fg placeholder:text-fg-subtle transition-colors hover:border-fg-subtle focus-visible:border-brand disabled:opacity-50';

export function Input({ invalid, className, ...rest }: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      aria-invalid={invalid || undefined}
      className={cx(FIELD, invalid && 'border-danger', className)}
      {...rest}
    />
  );
}

export function Textarea({
  invalid,
  className,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  return (
    <textarea
      aria-invalid={invalid || undefined}
      className={cx(FIELD, 'min-h-24 resize-y', invalid && 'border-danger', className)}
      {...rest}
    />
  );
}

// SRS 3.9.1: a password field needs a visibility toggle. It is a real <button type="button"> (focusable,
// keyboard operable, announced with its state) and must never submit the surrounding form.
export function PasswordInput({
  className,
  ...rest
}: Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> & { invalid?: boolean }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input type={visible ? 'text' : 'password'} className={cx('pr-11', className)} {...rest} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Hide password' : 'Show password'}
        aria-pressed={visible}
        className="absolute inset-y-0 right-0 flex items-center px-3 text-fg-muted transition-colors hover:text-fg"
      >
        {visible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
      </button>
    </div>
  );
}
