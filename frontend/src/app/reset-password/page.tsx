'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { supabase } from '../../lib/supabase';
import { AUTH_LINK, AuthLayout } from '../../components/auth/AuthLayout';
import { Button } from '../../components/ui/Button';
import { FormField } from '../../components/ui/FormField';
import { PasswordInput } from '../../components/ui/Input';
import { Notice } from '../../components/ui/Notice';

const MIN_LENGTH = 6;

type Status = 'checking' | 'ready' | 'invalid' | 'done';
type FieldError = { field: 'password' | 'confirm'; message: string };

// Landing page for the link in the recovery email. Supabase turns that link into a
// short-lived session (event PASSWORD_RECOVERY); without one there is nothing this
// page is allowed to do, so it says so instead of showing a form that cannot work.
export default function ResetPassword() {
  const [status, setStatus] = useState<Status>('checking');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [fieldError, setFieldError] = useState<FieldError | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'PASSWORD_RECOVERY' || (event === 'INITIAL_SESSION' && session)) {
        setStatus('ready');
      } else if (event === 'INITIAL_SESSION' && !session) {
        // Only "invalid" if a recovery event hasn't already made the form ready.
        setStatus((current) => (current === 'ready' ? current : 'invalid'));
      }
    });
    return () => subscription.unsubscribe();
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFieldError(null);

    if (password.length < MIN_LENGTH) {
      setFieldError({ field: 'password', message: `Password must be at least ${MIN_LENGTH} characters.` });
      return;
    }
    if (password !== confirm) {
      setFieldError({ field: 'confirm', message: 'The two passwords do not match.' });
      return;
    }

    setLoading(true);
    const { error: updateError } = await supabase.auth.updateUser({ password });
    if (updateError) {
      setError(updateError.message);
      setLoading(false);
      return;
    }
    // The recovery session was only meant for this one change.
    await supabase.auth.signOut();
    setStatus('done');
    setLoading(false);
  };

  return (
    <AuthLayout title="Choose a new password">
      {status === 'checking' && (
        <p role="status" className="text-app text-fg-muted">
          Verifying your reset link…
        </p>
      )}

      {status === 'invalid' && (
        <Notice tone="danger" role="alert" title="This link is invalid or has expired">
          Reset links can only be used once and expire quickly. Request a new one to continue.
          <div className="mt-4">
            <Link href="/forgot-password" className={AUTH_LINK}>
              Request a new link
            </Link>
          </div>
        </Notice>
      )}

      {status === 'done' && (
        <Notice tone="success" role="status" title="Password updated">
          You can now sign in with your new password.
          <div className="mt-4">
            <Link href="/login" className={AUTH_LINK}>
              Go to sign in
            </Link>
          </div>
        </Notice>
      )}

      {status === 'ready' && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {error && (
            <Notice tone="danger" role="alert">
              {error}
            </Notice>
          )}

          <FormField
            label={`New password (min ${MIN_LENGTH} characters)`}
            error={fieldError?.field === 'password' ? fieldError.message : null}
          >
            {(field) => (
              <PasswordInput
                {...field}
                required
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            )}
          </FormField>

          <FormField label="Confirm new password" error={fieldError?.field === 'confirm' ? fieldError.message : null}>
            {(field) => (
              <PasswordInput
                {...field}
                required
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
              />
            )}
          </FormField>

          <Button type="submit" size="lg" disabled={loading} className="w-full">
            {loading ? 'Updating…' : 'Update password'}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
