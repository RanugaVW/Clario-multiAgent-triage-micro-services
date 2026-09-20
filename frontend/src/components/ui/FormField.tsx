'use client';

import { useId, type ReactNode } from 'react';

export interface FieldProps {
  id: string;
  'aria-describedby'?: string;
  invalid: boolean;
}

/**
 * Wires a visible label, an optional hint and an optional error to a field. The child is a function so it
 * receives the props to spread onto the input: `{(field) => <Input {...field} ... />}`. The error is an
 * alert so screen readers announce it when it appears.
 *
 * `{...field}` is only for components that accept `invalid` (Input, Textarea, PasswordInput). Spread onto a
 * native element, `invalid` leaks to the DOM as an unknown attribute.
 */
export function FormField({
  label,
  hint,
  error,
  children,
}: {
  label: string;
  hint?: string;
  error?: string | null;
  children: (field: FieldProps) => ReactNode;
}) {
  const id = useId();
  const hintId = `${id}-hint`;
  const errorId = `${id}-error`;
  const describedBy = [hint ? hintId : null, error ? errorId : null].filter(Boolean).join(' ') || undefined;

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={id} className="text-app font-medium text-fg">
        {label}
      </label>
      {children({ id, 'aria-describedby': describedBy, invalid: Boolean(error) })}
      {hint && (
        <p id={hintId} className="text-small text-fg-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} role="alert" className="text-small text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
