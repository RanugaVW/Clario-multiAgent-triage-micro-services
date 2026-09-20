'use client';

import { useState } from 'react';
import Link from 'next/link';
import { supabase } from '../../lib/supabase';
import { AUTH_LINK, AuthLayout } from '../../components/auth/AuthLayout';
import { Button } from '../../components/ui/Button';
import { FormField } from '../../components/ui/FormField';
import { Input } from '../../components/ui/Input';
import { Notice } from '../../components/ui/Notice';

// SRS 3.9.1 (Authentication Interface): "Forgot Password option". Sends a
// Supabase recovery email whose link lands on /reset-password.
export default function ForgotPassword() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/reset-password`,
    });

    if (resetError) {
      setError(resetError.message);
    } else {
      setSent(true);
    }
    setLoading(false);
  };

  return (
    <AuthLayout
      title="Reset password"
      description={
        sent
          ? undefined
          : "Enter the email address for your account and we'll send you a link to choose a new password."
      }
      footer={
        sent ? undefined : (
          <Link href="/login" className={AUTH_LINK}>
            Back to sign in
          </Link>
        )
      }
    >
      {sent ? (
        <Notice tone="success" role="status" title="Check your email" focusOnMount>
          {/* Deliberately identical whether or not the address has an account,
              so this form can't be used to discover who is registered. */}
          If an account exists for that address, we&apos;ve sent a link to reset your password.
          <div className="mt-4">
            <Link href="/login" className={AUTH_LINK}>
              Return to sign in
            </Link>
          </div>
        </Notice>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {error && (
            <Notice tone="danger" role="alert">
              {error}
            </Notice>
          )}

          <FormField label="Email address">
            {(field) => (
              <Input
                {...field}
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
              />
            )}
          </FormField>

          <Button type="submit" size="lg" disabled={loading} className="w-full">
            {loading ? 'Sending…' : 'Send reset link'}
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
