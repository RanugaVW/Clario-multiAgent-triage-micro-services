'use client';

import { Eye, EyeOff } from 'lucide-react';
import { useState, type ComponentProps } from 'react';
import { cx } from '../../lib/cx';

// 16 px below 640 px: iOS Safari zooms the whole page when a field under 16 px takes focus. From 640 px up the
// compact app size applies.
const FIELD =
  'w-full rounded-lg border bg-surface px-3.5 py-2.5 text-body sm:text-app text-fg placeholder:text-fg-subtle transition-colors disabled:opacity-50';

// Border colour is chosen per state, with the hover and focus variants included, so the error cue does not
// vanish exactly when the user interacts with the field.
const BORDER_VALID = 'border-border-strong hover:border-fg-subtle focus-visible:border-brand';
const BORDER_INVALID = 'border-danger hover:border-danger focus-visible:border-danger';

export function Input({ invalid, className, ...rest }: ComponentProps<'input'> & { invalid?: boolean }) {
  return (
    <input
      aria-invalid={invalid || undefined}
      className={cx(FIELD, invalid ? BORDER_INVALID : BORDER_VALID, className)}
      {...rest}
    />
  );
}

export function Textarea({ invalid, className, ...rest }: ComponentProps<'textarea'> & { invalid?: boolean }) {
  return (
    <textarea
      aria-invalid={invalid || undefined}
      className={cx(FIELD, invalid ? BORDER_INVALID : BORDER_VALID, 'min-h-24 resize-y', className)}
      {...rest}
    />
  );
}

// SRS 3.9.1: a password field needs a visibility toggle. It is a real <button type="button"> (focusable,
// keyboard operable, announced with its state) and must never submit the surrounding form. `type` is applied
// after `rest` so a caller cannot override it, and the toggle is disabled together with the input.
export function PasswordInput({
  className,
  ...rest
}: Omit<ComponentProps<'input'>, 'type'> & { invalid?: boolean }) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input {...rest} type={visible ? 'text' : 'password'} className={cx('pr-11', className)} />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        disabled={rest.disabled}
        aria-label={visible ? 'Hide password' : 'Show password'}
        aria-pressed={visible}
        className="absolute inset-y-0 right-0 flex items-center px-3 text-fg-muted transition-colors hover:text-fg disabled:opacity-50"
      >
        {visible ? <EyeOff className="h-4 w-4" aria-hidden="true" /> : <Eye className="h-4 w-4" aria-hidden="true" />}
      </button>
    </div>
  );
}
